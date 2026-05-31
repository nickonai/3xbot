"""Интеграция с ЮKassa: тарифы, создание платежа, проверка статуса.

REST API ЮKassa (https://yookassa.ru/developers):
  POST /v3/payments         — создать платёж (Basic Auth shopId:secret,
                              заголовок Idempotence-Key)
  GET  /v3/payments/{id}    — статус (pending / succeeded / canceled)

Бот работает без публичного сайта, поэтому подтверждение оплаты — опросом
статуса (polling), а не webhook. return_url ведёт обратно в бота.
"""

import os
import uuid

import requests

API = "https://api.yookassa.ru/v3"
HTTP_TIMEOUT = 30

# Тарифы. shots — сколько фотосессий начисляется.
PLAN_SINGLE = "single"
PLAN_SUB = "sub"

PLANS = {
    PLAN_SINGLE: {
        "title": "💎 Разовая — 100 ₽",
        "price": "100.00",
        "shots": 1,
        "is_sub": False,
        "description": "1 нейрофотосессия (4 фото)",
    },
    PLAN_SUB: {
        "title": "🔥 Подписка — 499 ₽/мес",
        "price": "499.00",
        "shots": 10,
        "is_sub": True,
        "description": "Подписка: 10 фотосессий в месяц",
    },
}

class PaymentError(Exception):
    pass


def is_configured() -> bool:
    return bool(os.environ.get("YOOKASSA_SHOP_ID", "").strip()
                and os.environ.get("YOOKASSA_SECRET_KEY", "").strip()
                and os.environ.get("YOOKASSA_RETURN_URL", "").strip())


def _auth() -> tuple[str, str]:
    shop = os.environ.get("YOOKASSA_SHOP_ID", "").strip()
    secret = os.environ.get("YOOKASSA_SECRET_KEY", "").strip()
    if not shop or not secret:
        raise PaymentError("YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY не заданы")
    return shop, secret


def _return_url() -> str:
    """Ссылка, куда ЮKassa вернёт пользователя после оплаты."""
    url = os.environ.get("YOOKASSA_RETURN_URL", "").strip()
    if not url:
        raise PaymentError("YOOKASSA_RETURN_URL не задан")
    return url


def create_payment(plan_id: str, user_key: str) -> dict:
    """Создаёт платёж и возвращает {id, confirmation_url}."""
    plan = PLANS[plan_id]
    body = {
        "amount": {"value": plan["price"], "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": _return_url()},
        "description": plan["description"],
        "metadata": {"user_key": user_key, "plan": plan_id},
    }
    headers = {
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(f"{API}/payments", json=body, headers=headers,
                          auth=_auth(), timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise PaymentError(f"сеть ЮKassa недоступна: {e}") from e

    if r.status_code not in (200, 201):
        raise PaymentError(f"ЮKassa вернула {r.status_code}: {r.text[:300]}")

    data = r.json()
    url = data.get("confirmation", {}).get("confirmation_url")
    if not data.get("id") or not url:
        raise PaymentError(f"некорректный ответ ЮKassa: {data}")
    return {"id": data["id"], "confirmation_url": url}


def get_status(payment_id: str) -> str:
    """Возвращает статус платежа: pending / succeeded / canceled / unknown."""
    try:
        r = requests.get(f"{API}/payments/{payment_id}", auth=_auth(),
                         timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise PaymentError(f"сеть ЮKassa недоступна: {e}") from e
    if r.status_code != 200:
        raise PaymentError(f"ЮKassa вернула {r.status_code}: {r.text[:200]}")
    return r.json().get("status", "unknown")
