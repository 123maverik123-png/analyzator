# main.py
import os
import json
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import WATCH_FOLDER, SUPPORTED_EXTENSIONS, OUTPUT_FOLDER
from transcriber import transcribe_audio
from analyzer import analyze_full
from storage import init_db, already_processed, save_call
from sender import flush_pending

def _write_json_atomic(path, data):
    """Пишет JSON атомарно: сначала во временный файл рядом, потом os.replace().
    Защищает от повреждённых/частично записанных отчётов при параллельном
    доступе (например, GUI и main.py одновременно) или сбое в процессе записи —
    читатель никогда не увидит файл в промежуточном состоянии."""
    tmp_path = f"{path}.tmp{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return

        print(f"[{datetime.now()}] Обнаружен новый файл: {file_path}")

        call_id = os.path.basename(file_path)
        if already_processed(call_id):
            print("  -> Уже обработан ранее, пропускаем.")
            return

        # Ждём, пока файл допишется
        if not self.wait_for_file_stable(file_path):
            print("  -> Пропускаем (таймаут).")
            return

        try:
            print("  -> Начинаем распознавание...")
            transcribe_result = transcribe_audio(file_path, call_id=call_id)
            transcript = transcribe_result.get("full_text")

            if not transcript:
                print("  -> Распознавание не дало текста (возможно, тишина).")
                return

            print(f"  -> Распознано {len(transcript)} символов.")
            if transcribe_result.get("diarized"):
                n_speakers = len({t["speaker"] for t in transcribe_result["turns"]})
                print(f"  -> Диаризация: найдено {n_speakers} голос(а/ов), "
                      f"{len(transcribe_result['turns'])} реплик(и).")
                analysis_text = transcribe_result.get("dialogue_text") or transcript
            else:
                analysis_text = transcript

            print("  -> Анализируем текст...")
            result = analyze_full(transcript, llm_input_text=analysis_text)
            # full_text в отчёте — исходная сплошная расшифровка (для поиска/чтения),
            # дополнительно сохраняем разбивку по репликам, если диаризация сработала.
            result["diarized"] = transcribe_result.get("diarized", False)
            if transcribe_result.get("diarized"):
                result["dialogue_text"] = transcribe_result["dialogue_text"]
                result["turns"] = transcribe_result["turns"]

            report_name = f"{call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            report_path = os.path.join(OUTPUT_FOLDER, report_name)
            _write_json_atomic(report_path, result)
            print(f"  -> Отчёт сохранён: {report_path}")

            # Сохраняем в локальную БД и пытаемся отправить метрики в центр
            save_call(call_id, result)
            flush_pending()

            if "llm_analysis" in result and "problem" in result["llm_analysis"]:
                print(f"  -> Проблема: {result['llm_analysis']['problem']}")
            print(f"  -> Тональность: {result['sentiment']}")

        except Exception as e:
            print(f"  -> ОШИБКА при обработке {file_path}: {e}")

    def wait_for_file_stable(self, file_path, timeout=60, check_interval=1, stable_checks=3):
        print("  -> Ожидаем завершения записи файла...")
        last_size = -1
        stable_count = 0
        elapsed = 0

        while elapsed < timeout:
            if not os.path.exists(file_path):
                return False

            current_size = os.path.getsize(file_path)
            if current_size == last_size:
                stable_count += 1
                if stable_count >= stable_checks:
                    print(f"  -> Файл стабилен (размер {current_size} байт).")
                    return True
            else:
                stable_count = 0
                last_size = current_size

            time.sleep(check_interval)
            elapsed += check_interval

        print(f"  -> Таймаут ({timeout} сек) – файл, возможно, не дописался.")
        return False


def main():
    init_db()

    if not os.path.exists(WATCH_FOLDER):
        print(f"Папка {WATCH_FOLDER} не существует. Создаю...")
        os.makedirs(WATCH_FOLDER)

    # Досылаем то, что накопилось, пока оператор был оффлайн
    flush_pending()

    print(f"Начинаю следить за папкой: {WATCH_FOLDER}")
    event_handler = AudioHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        ticks = 0
        while True:
            time.sleep(1)
            ticks += 1
            if ticks >= 60:  # раз в минуту пробуем досылать очередь
                ticks = 0
                flush_pending()
    except KeyboardInterrupt:
        observer.stop()
        print("\nБот остановлен.")
    observer.join()

if __name__ == "__main__":
    main()