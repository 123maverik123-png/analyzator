# sender.py — отправка метрик звонков в центральный сервис.
# Отправляются ТОЛЬКО метрики (без аудио и без полного текста разговора).
# Если центр недоступен (оператор оффлайн) — данные остаются в очереди и досылаются позже.
import os
import requests
from config import CENTRAL_URL, CENTRAL_TOKEN, MACHINE_ID
from storage import get_pending, mark_sent

# Проверка TLS-сертификата. Для самоподписанного сертификата внутри WireGuard
# можно выставить CENTRAL_VERIFY_TLS=0 (трафик и так шифруется туннелем).
_VERIFY = os.getenv("CENTRAL_VERIFY_TLS", "1") != "0"
_TIMEOUT = 15


def flush_pending():
    """Досылает в центр все накопленные неотправленные метрики. Возвращает число отправленных."""
    if not CENTRAL_URL:
        return 0  # автономный режим — центр не настроен

    pending = get_pending()
    if not pending:
        return 0

    try:
        resp = requests.post(
            f"{CENTRAL_URL}/api/results",
            json={"machine_id": MACHINE_ID, "results": pending},
            headers={"Authorization": f"Bearer {CENTRAL_TOKEN}"},
            timeout=_TIMEOUT,
            verify=_VERIFY,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  -> Центр недоступен, метрики останутся в очереди: {e}")
        return 0

    sent_ids = [item["call_id"] for item in pending]
    mark_sent(sent_ids)
    print(f"  -> Отправлено в центр: {len(sent_ids)} записей.")
    return len(sent_ids)
