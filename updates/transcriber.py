# transcriber.py — распознавание речи (faster-whisper) + диаризация спикеров (pyannote.audio).
#
# Записи моно (один канал на оператора и абонента вместе), поэтому разделение "кто
# говорил" делается по тембру голоса, а не по аудиоканалам. Диаризация даёт интервалы
# времени с меткой спикера (SPEAKER_00/SPEAKER_01); сопоставляем их с сегментами текста
# от Whisper по максимальному пересечению по времени.
import os
from config import (
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE,
    DIARIZATION_ENABLED, DIARIZATION_MODEL, DIARIZATION_NUM_SPEAKERS, HF_TOKEN,
)

_whisper_model = None
_diarization_pipeline = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print(f"Загрузка модели Whisper ({WHISPER_MODEL})...")
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE
        )
        print("Модель Whisper загружена.")
    return _whisper_model


def get_diarization_pipeline():
    """Лениво загружает pipeline диаризации. Возвращает None, если диаризация
    выключена в конфиге или модель не удалось загрузить (например, нет HF_TOKEN
    или нет сети) — в этом случае вызывающий код должен продолжить без неё."""
    global _diarization_pipeline
    if not DIARIZATION_ENABLED:
        return None
    if _diarization_pipeline is None:
        try:
            from pyannote.audio import Pipeline
            if not HF_TOKEN:
                print("  -> HF_TOKEN не задан в secret.env — диаризация недоступна, "
                      "распознавание продолжится без разделения голосов.")
                _diarization_pipeline = False
                return None
            print(f"Загрузка модели диаризации ({DIARIZATION_MODEL})...")
            _diarization_pipeline = Pipeline.from_pretrained(
                DIARIZATION_MODEL, token=HF_TOKEN
            )
            print("Модель диаризации загружена.")
        except Exception as e:
            print(f"  -> Диаризация недоступна ({e}), продолжаем без разделения голосов.")
            _diarization_pipeline = False  # запоминаем неудачу, чтобы не пытаться на каждом файле
    return _diarization_pipeline or None


def _run_diarization(file_path):
    """Возвращает список (start, end, speaker_label) или [] при ошибке/отсутствии модели."""
    pipeline = get_diarization_pipeline()
    if pipeline is None:
        return []
    try:
        output = pipeline(file_path, num_speakers=DIARIZATION_NUM_SPEAKERS)
    except Exception as e:
        print(f"  -> Ошибка диаризации: {e}")
        return []

    # community-1 отдаёт output.speaker_diarization (Annotation),
    # 3.1 и более старые pipeline возвращают Annotation напрямую.
    annotation = getattr(output, "speaker_diarization", output)
    turns = []
    try:
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            turns.append((turn.start, turn.end, speaker))
    except AttributeError:
        return []
    return turns


def _overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _assign_speakers(segments, turns):
    """Сопоставляет каждый сегмент текста Whisper с спикером диаризации
    по максимальному пересечению по времени. Возвращает список реплик:
    [{"speaker": "SPEAKER_00", "start": .., "end": .., "text": ..}, ...]
    Соседние сегменты одного спикера склеиваются в одну реплику."""
    raw = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        speaker = None
        if turns:
            best_overlap, best_speaker = 0.0, None
            for t_start, t_end, t_speaker in turns:
                ov = _overlap(seg.start, seg.end, t_start, t_end)
                if ov > best_overlap:
                    best_overlap, best_speaker = ov, t_speaker
            speaker = best_speaker
        raw.append({"speaker": speaker, "start": seg.start, "end": seg.end, "text": text})

    # Склеиваем подряд идущие сегменты одного спикера в одну реплику
    merged = []
    for item in raw:
        if merged and merged[-1]["speaker"] == item["speaker"]:
            merged[-1]["end"] = item["end"]
            merged[-1]["text"] += " " + item["text"]
        else:
            merged.append(dict(item))
    return merged


def _label_roles(turns_or_segments, call_id):
    """Эвристически определяет, кто из спикеров — оператор, а кто — абонент.
    ТОЧНОГО способа узнать это из аудио нет — используем эвристику: первым
    в разговоре говорит оператор (приветствие/представление), как для исходящих,
    так и для входящих звонков (отвечает на линию). Если эвристика для вашего
    сценария не подходит — роли всё равно можно посмотреть по сырым меткам
    SPEAKER_00/SPEAKER_01 и таймингам в full_text_diarized."""
    order = []
    for item in turns_or_segments:
        sp = item.get("speaker") if isinstance(item, dict) else None
        if sp is not None and sp not in order:
            order.append(sp)
    role_by_speaker = {}
    if len(order) >= 1:
        role_by_speaker[order[0]] = "Оператор"
    if len(order) >= 2:
        role_by_speaker[order[1]] = "Абонент"
    # Спикеров может оказаться больше двух (шум/третий голос) — помечаем как есть
    for extra in order[2:]:
        role_by_speaker[extra] = extra
    return role_by_speaker


def transcribe_audio(file_path, call_id=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    model = get_whisper_model()
    segments, info = model.transcribe(file_path, language="ru", beam_size=3, best_of=1)
    segments = list(segments)  # faster-whisper отдаёт генератор, материализуем один раз

    full_text = " ".join(seg.text.strip() for seg in segments).strip()

    turns = _run_diarization(file_path)
    if not turns:
        # Диаризация недоступна/выключена — отдаём как раньше, без разделения голосов.
        return {"full_text": full_text, "diarized": False, "turns": []}

    replicas = _assign_speakers(segments, turns)
    role_by_speaker = _label_roles(replicas, call_id)

    dialogue_lines = []
    for r in replicas:
        role = role_by_speaker.get(r["speaker"], r["speaker"] or "?")
        dialogue_lines.append(f"[{role}] {r['text']}")

    return {
        "full_text": full_text,
        "diarized": True,
        "dialogue_text": "\n".join(dialogue_lines),
        "turns": [
            {
                "speaker": role_by_speaker.get(r["speaker"], r["speaker"] or "?"),
                "start": round(r["start"], 2),
                "end": round(r["end"], 2),
                "text": r["text"],
            }
            for r in replicas
        ],
    }
