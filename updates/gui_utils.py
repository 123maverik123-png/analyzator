# gui_utils.py — утилиты для форматирования и парсинга
def fmt_time(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def extract_phone(call_id):
    parts = call_id.split("-")
    return parts[2][:11] if len(parts) >= 3 else "—"


def extract_dt(call_id):
    parts = call_id.split("-")
    if len(parts) >= 2 and len(parts[0]) == 8 and len(parts[1]) >= 4:
        d, t = parts[0], parts[1]
        return f"{d[6:8]}.{d[4:6]}.{d[0:4]} {t[0:2]}:{t[2:4]}"
    return "—"