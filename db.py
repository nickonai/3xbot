"""SQLite-хранилище баланса генераций и подписок.

Одна «фотосессия» = одна генерация (4 фото). Баланс пользователя складывается
из двух источников:
  - credits        — разовые оплаченные генерации (тариф 100 ₽);
  - sub_credits     — остаток фотосессий по активной подписке (499 ₽/мес),
                      действителен до sub_until (unix-время).

Списание идёт сначала с подписки (если активна), потом с разовых.

Ключ пользователя — строка вида "tg:123" / "vk:456" / "max:789" (как в dialog).
Потокобезопасно: один Connection + Lock (у нас 3 потока платформ + потоки
поллинга платежей).
"""

import sqlite3
import threading
import time

_DB_PATH = "bot.db"
_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def init(path: str = _DB_PATH) -> None:
    global _conn
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_key   TEXT PRIMARY KEY,
            credits    INTEGER NOT NULL DEFAULT 0,
            sub_credits INTEGER NOT NULL DEFAULT 0,
            sub_until  INTEGER NOT NULL DEFAULT 0
        )
    """)
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            user_key   TEXT NOT NULL,
            plan       TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL
        )
    """)
    _conn.commit()


def _ensure(user_key: str) -> None:
    _conn.execute("INSERT OR IGNORE INTO users(user_key) VALUES (?)", (user_key,))


def balance(user_key: str) -> dict:
    """Текущий баланс: {credits, sub_credits, sub_until, sub_active, total}."""
    with _lock:
        _ensure(user_key)
        row = _conn.execute(
            "SELECT credits, sub_credits, sub_until FROM users WHERE user_key=?",
            (user_key,),
        ).fetchone()
        _conn.commit()
    credits, sub_credits, sub_until = row
    sub_active = sub_until > time.time() and sub_credits > 0
    return {
        "credits": credits,
        "sub_credits": sub_credits if sub_active else 0,
        "sub_until": sub_until,
        "sub_active": sub_active,
        "total": credits + (sub_credits if sub_active else 0),
    }


def has_generation(user_key: str) -> bool:
    return balance(user_key)["total"] > 0


def consume_generation(user_key: str) -> bool:
    """Списывает одну генерацию (сначала с подписки, потом разовую).

    Возвращает True, если списание удалось; False — если нечего списывать.
    """
    with _lock:
        _ensure(user_key)
        row = _conn.execute(
            "SELECT credits, sub_credits, sub_until FROM users WHERE user_key=?",
            (user_key,),
        ).fetchone()
        credits, sub_credits, sub_until = row
        sub_active = sub_until > time.time() and sub_credits > 0

        if sub_active:
            _conn.execute(
                "UPDATE users SET sub_credits = sub_credits - 1 WHERE user_key=?",
                (user_key,),
            )
        elif credits > 0:
            _conn.execute(
                "UPDATE users SET credits = credits - 1 WHERE user_key=?",
                (user_key,),
            )
        else:
            _conn.commit()
            return False
        _conn.commit()
        return True


def add_credits(user_key: str, n: int) -> None:
    """Начисляет n разовых генераций (тариф 100 ₽)."""
    with _lock:
        _ensure(user_key)
        _conn.execute(
            "UPDATE users SET credits = credits + ? WHERE user_key=?",
            (n, user_key),
        )
        _conn.commit()


def grant_subscription(user_key: str, shots: int, days: int = 30) -> None:
    """Активирует подписку: shots фотосессий на days дней.

    Если подписка уже активна — продлевает срок и добавляет фотосессии.
    """
    now = int(time.time())
    with _lock:
        _ensure(user_key)
        row = _conn.execute(
            "SELECT sub_credits, sub_until FROM users WHERE user_key=?",
            (user_key,),
        ).fetchone()
        cur_credits, cur_until = row
        base = cur_until if cur_until > now else now
        new_until = base + days * 86400
        # Если старая подписка истекла — начинаем счёт заново.
        new_credits = (cur_credits if cur_until > now else 0) + shots
        _conn.execute(
            "UPDATE users SET sub_credits=?, sub_until=? WHERE user_key=?",
            (new_credits, new_until, user_key),
        )
        _conn.commit()


# --- Платежи (для polling статуса) ----------------------------------------

def create_payment(payment_id: str, user_key: str, plan: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO payments(payment_id, user_key, plan, status, "
            "created_at) VALUES (?, ?, ?, 'pending', ?)",
            (payment_id, user_key, plan, int(time.time())),
        )
        _conn.commit()


def mark_payment(payment_id: str, status: str) -> None:
    with _lock:
        _conn.execute(
            "UPDATE payments SET status=? WHERE payment_id=?",
            (status, payment_id),
        )
        _conn.commit()


def pending_payments(max_age_sec: int = 3600) -> list[dict]:
    """Незавершённые платежи не старше max_age_sec — для опроса статуса."""
    cutoff = int(time.time()) - max_age_sec
    with _lock:
        rows = _conn.execute(
            "SELECT payment_id, user_key, plan FROM payments "
            "WHERE status='pending' AND created_at >= ?",
            (cutoff,),
        ).fetchall()
        _conn.commit()
    return [{"payment_id": p, "user_key": u, "plan": pl} for p, u, pl in rows]


def clear_all_balances() -> int:
    """Обнуляет баланс ВСЕХ пользователей и закрывает зависшие платежи.

    Возвращает число затронутых пользователей. Административная операция.
    """
    with _lock:
        n = _conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        _conn.execute("UPDATE users SET credits=0, sub_credits=0, sub_until=0")
        _conn.execute("UPDATE payments SET status='canceled' WHERE status='pending'")
        _conn.commit()
    return n
