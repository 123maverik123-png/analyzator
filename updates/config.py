# config.py
import os
from dotenv import load_dotenv

# Версия приложения (менять при каждом релизе)
VERSION = "1.0.0"
# Базовый URL для проверки обновлений (папка updates в репозитории)
UPDATE_BASE_URL = "https://raw.githubusercontent.com/ваш-username/ваш-репозиторий/main/updates"

# Файл с секретами (YC_API_KEY, YC_FOLDER_ID, CENTRAL_TOKEN)
SECRET_FILE = os.path.join(os.path.dirname(__file__), "secret.env")
load_dotenv(SECRET_FILE)

# Путь к папке с записями — берётся из пользовательских настроек (меняется в GUI).
import settings as _settings
WATCH_FOLDER = _settings.get("recordings_folder")

# Поддерживаемые расширения аудиофайлов
SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")

# Параметры Whisper
WHISPER_MODEL = "medium"      # "large-v3" точнее, но медленнее; medium — баланс
WHISPER_DEVICE = "cpu"        # CPU-сборка torch; для GPU нужен torch с CUDA и device="cuda"
WHISPER_COMPUTE = "int8"      # int8 — быстро и экономно на CPU

# ---------- Диаризация (разделение голосов оператор/абонент) ----------
DIARIZATION_ENABLED = os.getenv("DIARIZATION_ENABLED", "1") != "0"
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1")
HF_TOKEN = os.getenv("HF_TOKEN", "")
DIARIZATION_NUM_SPEAKERS = 2

# Папка для отчётов (создаётся автоматически)
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Модель для тональности (будет скачана из Hugging Face)
SENTIMENT_MODEL = "blanchefort/rubert-base-cased-sentiment"

# ---------- Идентификация оператора и связь с центром ----------
OPERATOR_ID = (os.getenv("OPERATOR_ID") or _settings.get("operator_id")
               or os.getenv("COMPUTERNAME") or "unknown")


def _machine_id():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        val, _ = winreg.QueryValueEx(k, "MachineGuid")
        winreg.CloseKey(k)
        return val
    except Exception:
        import uuid
        return f"{uuid.getnode():012x}"


MACHINE_ID = _machine_id()

CENTRAL_URL = os.getenv("CENTRAL_URL", "").rstrip("/")
CENTRAL_TOKEN = os.getenv("CENTRAL_TOKEN", "")
LOCAL_DB = os.path.join(os.path.dirname(__file__), "calls_local.db")