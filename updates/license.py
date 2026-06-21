# license.py — работа с лицензией (демо, активация, проверка)
import os
import json
import requests
from datetime import datetime, timedelta
from config import CENTRAL_URL, MACHINE_ID

LICENSE_FILE = os.path.join(os.path.dirname(__file__), "license_cache.json")
LICENSE_SERVER = CENTRAL_URL  # тот же сервер, что и для статистики

def _load_cache():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_cache(data):
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _request(endpoint, data):
    """Отправляет запрос на сервер лицензирования."""
    url = f"{LICENSE_SERVER}{endpoint}"
    try:
        resp = requests.post(url, json=data, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"status": "error", "detail": resp.text}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

def get_license_status():
    """
    Проверяет статус лицензии.
    Возвращает:
        'trial' – демо-период активен
        'active' – платная подписка активна
        'expired' – истекло
        'error' – ошибка (сервер недоступен)
        'not_found' – лицензия не найдена (не начинался триал)
    """
    # Сначала пробуем кэш
    cache = _load_cache()
    if cache and cache.get("status") in ("trial", "active"):
        end_date = cache.get("end_date")
        if end_date and datetime.now().isoformat() < end_date:
            # Кэш ещё валиден
            return cache.get("status")

    # Если кэш невалиден или отсутствует, обращаемся к серверу
    if not LICENSE_SERVER:
        return "error"

    result = _request("/license/verify", {"device_id": MACHINE_ID})
    if result.get("status") == "not_found":
        # Это первый запуск – автоматически начинаем триал
        trial_result = _request("/license/trial", {"device_id": MACHINE_ID})
        if trial_result.get("status") in ("trial", "active"):
            _save_cache({"status": trial_result["status"], "end_date": trial_result.get("end_date")})
            return trial_result["status"]
        else:
            return "error"
    elif result.get("status") in ("trial", "active"):
        _save_cache({"status": result["status"], "end_date": result.get("end_date")})
        return result["status"]
    elif result.get("status") == "expired":
        return "expired"
    else:
        return "error"

def activate_license(license_key):
    """Активирует платную подписку по ключу."""
    result = _request("/license/activate", {"device_id": MACHINE_ID, "license_key": license_key})
    if result.get("status") == "active":
        _save_cache({"status": "active", "end_date": result.get("end_date")})
        return True, "Подписка активирована до " + result.get("end_date")
    else:
        return False, result.get("detail", "Ошибка активации")

def days_remaining():
    """Возвращает количество дней до окончания лицензии (или 0, если не активно)."""
    cache = _load_cache()
    end_date_str = cache.get("end_date")
    if not end_date_str:
        return 0
    end = datetime.fromisoformat(end_date_str)
    delta = end - datetime.now()
    return max(0, delta.days)