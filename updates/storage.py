# storage.py — локальное хранилище звонков на ПК оператора (SQLite).
# Полные данные (включая текст разговора) остаются здесь и НЕ уходят в центр.
import json
import sqlite3
from datetime import datetime
from config import LOCAL_DB, OPERATOR_ID


def _connect():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                call_id       TEXT PRIMARY KEY,   -- имя файла записи, защищает от повторной обработки
                operator_id   TEXT NOT NULL,
                processed_at  TEXT NOT NULL,
                category      TEXT,
                problem       TEXT,
                action        TEXT,
                summary       TEXT,
                is_resolved   INTEGER,            -- 0/1
                sent_neg      REAL,
                sent_neu      REAL,
                sent_pos      REAL,
                full_text     TEXT,               -- остаётся ТОЛЬКО локально
                dialogue_text TEXT,                -- расшифровка с метками [Оператор]/[Абонент], если есть диаризация
                sent_status   INTEGER NOT NULL DEFAULT 0  -- 0=ожидает отправки, 1=отправлено
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                code        TEXT PRIMARY KEY,
                unlocked_at TEXT NOT NULL
            )
        """)
        # Миграция для баз, созданных до появления диаризации (столбца ещё нет).
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(calls)")}
        if "dialogue_text" not in existing_cols:
            conn.execute("ALTER TABLE calls ADD COLUMN dialogue_text TEXT")


def already_processed(call_id):
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        return row is not None


def save_call(call_id, result):
    """Сохраняет результат анализа локально. Возвращает False, если звонок уже был обработан."""
    llm = result.get("llm_analysis", {}) or {}
    sent = result.get("sentiment", {}) or {}
    is_resolved = 1 if llm.get("is_resolved") else 0
    try:
        with _connect() as conn:
            conn.execute("""
                INSERT INTO calls (call_id, operator_id, processed_at, category, problem,
                                   action, summary, is_resolved, sent_neg, sent_neu, sent_pos,
                                   full_text, dialogue_text, sent_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                call_id, OPERATOR_ID, datetime.now().isoformat(timespec="seconds"),
                llm.get("category"), llm.get("problem"), llm.get("action"), llm.get("summary"),
                is_resolved, sent.get("negative"), sent.get("neutral"), sent.get("positive"),
                result.get("full_text"), result.get("dialogue_text"),
            ))
        return True
    except sqlite3.IntegrityError:
        return False  # дубликат по call_id


def get_pending(limit=200):
    """Возвращает метрики звонков, ещё не отправленных в центр (БЕЗ полного текста)."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT call_id, operator_id, processed_at, category, problem, action,
                   summary, is_resolved, sent_neg, sent_neu, sent_pos
            FROM calls WHERE sent_status = 0 ORDER BY processed_at LIMIT ?
        """, (limit,)).fetchall()
    return [{
        "call_id": r["call_id"],
        "operator_id": r["operator_id"],
        "processed_at": r["processed_at"],
        "category": r["category"],
        "problem": r["problem"],
        "action": r["action"],
        "summary": r["summary"],
        "is_resolved": bool(r["is_resolved"]),
        "sentiment": {"negative": r["sent_neg"], "neutral": r["sent_neu"], "positive": r["sent_pos"]},
    } for r in rows]


def mark_sent(call_ids):
    if not call_ids:
        return
    with _connect() as conn:
        conn.executemany("UPDATE calls SET sent_status = 1 WHERE call_id = ?",
                         [(cid,) for cid in call_ids])


# ---------- Чтение для GUI ----------
def get_all_calls():
    """Список звонков для таблицы (без полного текста), новые сверху."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT call_id, operator_id, processed_at, category, problem,
                   is_resolved, sent_status
            FROM calls ORDER BY processed_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_call(call_id):
    """Полная карточка звонка, включая текст разговора."""
    with _connect() as conn:
        r = conn.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
    return dict(r) if r else None


def count_calls():
    """Число звонков — для определения изменений в фоновом наблюдателе."""
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]


# ---------- Статистика для геймификации ----------
def get_stats():
    """Сводные показатели оператора для расчёта достижений и XP."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM calls WHERE is_resolved=1").fetchone()[0]
        positive = conn.execute("SELECT COUNT(*) FROM calls WHERE sent_pos >= 0.6").fetchone()[0]
        # максимум звонков за один день
        max_day = conn.execute("""
            SELECT MAX(c) FROM (
                SELECT COUNT(*) c FROM calls GROUP BY substr(processed_at,1,10)
            )
        """).fetchone()[0] or 0
        # самая длинная серия решённых подряд (по времени обработки)
        flags = [r[0] for r in conn.execute(
            "SELECT is_resolved FROM calls ORDER BY processed_at")]
    best_streak = streak = 0
    for f in flags:
        streak = streak + 1 if f else 0
        best_streak = max(best_streak, streak)
    return {
        "total": total,
        "resolved": resolved,
        "positive": positive,
        "max_day": max_day,
        "best_streak": best_streak,
    }


# ---------- Достижения ----------
def get_unlocked():
    """Множество кодов уже разблокированных достижений."""
    with _connect() as conn:
        return {r[0] for r in conn.execute("SELECT code FROM achievements")}


def unlock(code):
    """Фиксирует достижение. True — если разблокировано впервые."""
    from datetime import datetime
    try:
        with _connect() as conn:
            conn.execute("INSERT INTO achievements (code, unlocked_at) VALUES (?, ?)",
                         (code, datetime.now().isoformat(timespec="seconds")))
        return True
    except sqlite3.IntegrityError:
        return False
