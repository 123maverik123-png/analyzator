# settings.py — пользовательские настройки оператора (папка записей, тема).
# Хранятся в %APPDATA%/bot_analyzer/settings.json (не в коде, у каждого свои).
import os
import json

_DEFAULT_RECORDINGS = "C:/Users/vanis/Desktop/Recordings"

_DIR = os.path.join(os.getenv("APPDATA") or os.path.dirname(__file__), "bot_analyzer")
_PATH = os.path.join(_DIR, "settings.json")

_DEFAULTS = {
    "recordings_folder": _DEFAULT_RECORDINGS,
    "theme": "dark",  # "dark" | "light"
    "operator_id": "",  # идентификатор оператора на этом ПК (привязка статистики)
}


def load():
    data = dict(_DEFAULTS)
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (FileNotFoundError, ValueError):
        pass
    return data


def save(data):
    os.makedirs(_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(key):
    return load().get(key, _DEFAULTS.get(key))


def set(key, value):
    data = load()
    data[key] = value
    save(data)
    return data
