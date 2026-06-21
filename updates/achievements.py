# achievements.py — геймификация: бейджи, очки опыта (XP) и уровни оператора.
import storage

# XP за обработанный звонок и бонус за решённый
XP_PER_CALL = 10
XP_PER_RESOLVED = 5

# Достижения: code, иконка, название, описание, метрика (ключ из storage.get_stats), цель.
ACHIEVEMENTS = [
    {"code": "first_call",   "icon": "🎧", "title": "Первый разговор", "desc": "Обработать первый звонок",        "metric": "total",       "target": 1},
    {"code": "calls_10",     "icon": "🔥", "title": "Разогрев",         "desc": "Обработать 10 звонков",            "metric": "total",       "target": 10},
    {"code": "calls_50",     "icon": "💪", "title": "Полста",           "desc": "Обработать 50 звонков",            "metric": "total",       "target": 50},
    {"code": "calls_100",    "icon": "🏆", "title": "Сотня",            "desc": "Обработать 100 звонков",           "metric": "total",       "target": 100},
    {"code": "resolved_50",  "icon": "✅", "title": "Решала",           "desc": "Решить 50 обращений",              "metric": "resolved",    "target": 50},
    {"code": "streak_10",    "icon": "⚡", "title": "В ударе",          "desc": "10 решённых подряд",               "metric": "best_streak", "target": 10},
    {"code": "day_20",       "icon": "🏃", "title": "Марафон",          "desc": "20 звонков за один день",          "metric": "max_day",     "target": 20},
    {"code": "positive_25",  "icon": "🌟", "title": "Лучик позитива",   "desc": "25 разговоров с позитивом",        "metric": "positive",    "target": 25},
]


def xp_for(stats):
    """Очки опыта по статистике оператора."""
    return stats["total"] * XP_PER_CALL + stats["resolved"] * XP_PER_RESOLVED


def level_info(xp):
    """Возвращает (уровень, xp_на_уровне, xp_до_следующего, доля_прогресса)."""
    level, acc, needed = 1, 0, 100
    while xp >= acc + needed:
        acc += needed
        level += 1
        needed = level * 100
    into = xp - acc
    return level, into, needed, (into / needed if needed else 0)


def evaluate(stats):
    """Список достижений с текущим прогрессом и статусом (для отрисовки карточек)."""
    unlocked = storage.get_unlocked()
    out = []
    for a in ACHIEVEMENTS:
        current = min(stats.get(a["metric"], 0), a["target"])
        out.append({
            **a,
            "current": current,
            "unlocked": a["code"] in unlocked or current >= a["target"],
            "progress": min(1.0, current / a["target"]) if a["target"] else 1.0,
        })
    return out


def sync_unlocks(stats):
    """Фиксирует только что выполненные достижения. Возвращает список новых (для уведомления)."""
    already = storage.get_unlocked()
    newly = []
    for a in ACHIEVEMENTS:
        if a["code"] not in already and stats.get(a["metric"], 0) >= a["target"]:
            if storage.unlock(a["code"]):
                newly.append(a)
    return newly
