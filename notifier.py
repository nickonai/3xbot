"""Реестр отправки сообщений пользователю по его user_key.

user_key имеет вид "<platform>:<native_id>", например "tg:123", "vk:456",
"max:789". Каждая платформа при старте регистрирует функцию отправки текста,
принимающую native_id. Это позволяет фоновому поллеру платежей уведомлять
пользователя в тот мессенджер, где он платил, без доступа к объекту-каналу.
"""

import threading
from collections.abc import Callable

# prefix ("tg"/"vk"/"max") -> callable(native_id: str, text: str)
_senders: dict[str, Callable[[str, str], None]] = {}
_lock = threading.Lock()


def register(prefix: str, send_text_fn: Callable[[str, str], None]) -> None:
    with _lock:
        _senders[prefix] = send_text_fn


def notify(user_key: str, text: str) -> bool:
    """Шлёт текст пользователю по его user_key. True, если отправлено."""
    prefix, _, native_id = user_key.partition(":")
    fn = _senders.get(prefix)
    if not fn or not native_id:
        return False
    try:
        fn(native_id, text)
        return True
    except Exception:  # noqa: BLE001 — уведомление не должно ронять поллер
        return False
