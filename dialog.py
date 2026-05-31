"""Платформо-независимая логика диалога бота нейрофотосессий.

FSM на пользователя:
    GENDER  -> ждём выбор пола (кнопкой) -> просим фото
    PHOTO   -> ждём фото -> генерируем 4 СЛУЧАЙНЫХ разных стиля параллельно
               -> отправляем -> снова ждём фото

Стиль пользователь НЕ выбирает: на каждое фото бот сам берёт 4 случайных
стиля из каталога и генерирует их одновременно.

Платформа предоставляет объект-«канал» с методами:
    send_text(text)
    send_buttons(text, options)       options: list[(payload, label)]
    send_photos(urls, caption)
    incoming.text                     текст входящего сообщения (или "")
    incoming.photo_bytes()            байты приложенного фото или None

Состояние хранится в памяти процесса (dict). Для продакшена — заменить на
Redis/БД, но для бота-демо этого достаточно.
"""

import random
import threading

import db
import payments
from generator import GenerationError, generate_parallel
from styles import STYLES, prompt_for


def _log(msg: str) -> None:
    print(f"[dialog] {msg}", flush=True)


# Состояния
S_GENDER = "gender"
S_PHOTO = "photo"

# Сколько разных кадров генерировать на одно фото.
SHOTS_PER_REQUEST = 4

# user_key -> dict состояния
_sessions: dict[str, dict] = {}
_lock = threading.Lock()


def _session(user_key: str) -> dict:
    with _lock:
        return _sessions.setdefault(user_key, {"state": S_GENDER})


def _reset(user_key: str) -> dict:
    with _lock:
        _sessions[user_key] = {"state": S_GENDER}
        return _sessions[user_key]


GREETING = (
    "👋 Привет! Я делаю креативные нейрофотосессии из твоего фото.\n\n"
    "Для начала выбери, какой стиль фигуры использовать:"
)

# Кнопки выбора пола: (payload, подпись).
GENDER_OPTIONS = [("male", "👨 Мужской"), ("female", "👩 Женский")]

ASK_PHOTO = (
    "📸 Отлично! Теперь пришли мне одно своё фото "
    "(лучше чёткое селфи, лицо хорошо видно).\n\n"
    "Я сделаю из него 4 разные креативные фотосессии 🎨"
)

# Кнопки тарифов: payload "buy:<plan_id>".
PAYWALL_TEXT = (
    "💳 Чтобы сделать фотосессию, выбери тариф:\n\n"
    "💎 *Разовая — 100 ₽* — одна фотосессия (4 фото)\n"
    "🔥 *Подписка — 499 ₽/мес* — 10 фотосессий в месяц\n\n"
    "После оплаты нажми «✅ Я оплатил»."
)

PLAN_OPTIONS = [
    (f"buy:{payments.PLAN_SINGLE}", payments.PLANS[payments.PLAN_SINGLE]["title"]),
    (f"buy:{payments.PLAN_SUB}", payments.PLANS[payments.PLAN_SUB]["title"]),
]

GENERATING = (
    "✨ Колдую над твоими 4 фотосессиями… Генерирую их параллельно, "
    "это займёт минуту-другую."
)


def _parse_gender(text: str) -> str | None:
    t = text.strip().lower()
    if t in ("male", "female"):              # payload от кнопки
        return t
    if t in ("м", "m", "муж", "мужской", "мужчина", "👨 мужской", "👨"):
        return "male"
    if t in ("ж", "f", "w", "жен", "женский", "женщина", "👩 женский", "👩"):
        return "female"
    return None


def _parse_plan(text: str) -> str | None:
    """Распознаёт тариф по payload ("buy:single") ИЛИ по подписи кнопки.

    В Telegram/VK reply-кнопки шлют подпись (напр. «🔥 Подписка — 499 ₽/мес»),
    а в MAX inline-callback шлёт payload «buy:sub» — поддерживаем оба варианта.
    """
    t = text.strip()
    if t.startswith("buy:"):
        plan_id = t.split(":", 1)[1]
        return plan_id if plan_id in payments.PLANS else None
    for plan_id, plan in payments.PLANS.items():
        if t == plan["title"]:
            return plan_id
    return None


def _pick_styles(n: int) -> list[dict]:
    """n случайных разных стилей (или все, если их меньше n)."""
    return random.sample(STYLES, min(n, len(STYLES)))


def _show_paywall(user_key: str, channel) -> None:
    channel.send_buttons(PAYWALL_TEXT, PLAN_OPTIONS)


def _balance_line(user_key: str) -> str:
    b = db.balance(user_key)
    parts = []
    if b["sub_active"]:
        parts.append(f"подписка: {b['sub_credits']} фотосессий")
    if b["credits"]:
        parts.append(f"разовых: {b['credits']}")
    return " · ".join(parts) if parts else "баланс пуст"


def _balance_greeting(user_key: str) -> str:
    """Человекочитаемый баланс для приветствия."""
    b = db.balance(user_key)
    if b["total"] <= 0:
        return "💳 У тебя пока нет доступных генераций."
    lines = [f"💼 Твой баланс: *{b['total']}* доступных фотосессий."]
    if b["sub_active"]:
        lines.append(f"   🔥 По подписке: {b['sub_credits']}")
    if b["credits"]:
        lines.append(f"   💎 Разовых: {b['credits']}")
    return "\n".join(lines)


def payment_success_text(user_key: str) -> str:
    """Текст уведомления об успешной оплате (общий для поллера и кнопки)."""
    return (
        f"✅ Оплата получена! Баланс: {_balance_line(user_key)}.\n\n"
        + ASK_PHOTO
    )


def on_payment_succeeded(user_key: str) -> None:
    """Вызывается при подтверждённой оплате: переводит диалог к приёму фото."""
    _session(user_key)["state"] = S_PHOTO


def _start_payment(user_key: str, plan_id: str, channel) -> None:
    """Создаёт платёж ЮKassa и отправляет пользователю ссылку."""
    if not payments.is_configured():
        channel.send_text("⚠️ Приём оплаты пока не настроен. Загляни позже.")
        return
    try:
        pay = payments.create_payment(plan_id, user_key)
    except payments.PaymentError as e:
        _log(f"{user_key}: ошибка создания платежа: {e}")
        channel.send_text(f"😔 Не удалось создать платёж: {e}")
        return
    db.create_payment(pay["id"], user_key, plan_id)
    _log(f"{user_key}: создан платёж {pay['id']} тариф {plan_id}")
    plan = payments.PLANS[plan_id]
    channel.send_text(
        f"💳 Оплата тарифа «{plan['title']}».\n\n"
        f"Перейди по ссылке и оплати:\n{pay['confirmation_url']}\n\n"
        "Как только оплата пройдёт, я сам пришлю подтверждение сюда — "
        "ждать и нажимать ничего не нужно 👌"
    )


def _check_payments(user_key: str, channel) -> bool:
    """Проверяет незавершённые платежи пользователя, начисляет при успехе.

    Возвращает True, если что-то зачислено.
    """
    granted = False
    for p in db.pending_payments():
        if p["user_key"] != user_key:
            continue
        try:
            status = payments.get_status(p["payment_id"])
        except payments.PaymentError as e:
            _log(f"{user_key}: ошибка проверки {p['payment_id']}: {e}")
            continue
        if status == "succeeded":
            _grant(p["user_key"], p["plan"])
            db.mark_payment(p["payment_id"], "succeeded")
            granted = True
        elif status == "canceled":
            db.mark_payment(p["payment_id"], "canceled")
    return granted


def _grant(user_key: str, plan_id: str) -> None:
    """Начисляет покупку на баланс."""
    plan = payments.PLANS[plan_id]
    if plan["is_sub"]:
        db.grant_subscription(user_key, plan["shots"], days=30)
    else:
        db.add_credits(user_key, plan["shots"])
    _log(f"{user_key}: начислен тариф {plan_id} (+{plan['shots']})")


def _run_generation(user_key: str, sess: dict, photo: bytes, channel) -> None:
    """Списывает генерацию и делает 4 случайные фотосессии."""
    if not db.consume_generation(user_key):
        _show_paywall(user_key, channel)
        return
    gender = sess.get("gender", "male")
    picked = _pick_styles(SHOTS_PER_REQUEST)
    prompts = [prompt_for(s, gender) for s in picked]
    names = ", ".join(s["id"] for s in picked)
    _log(f"{user_key}: фото ({len(photo)} б), пол {gender}, "
         f"стили [{names}] — генерирую {len(prompts)} параллельно")
    channel.send_text(GENERATING)
    try:
        urls = generate_parallel(photo, prompts)
    except GenerationError as e:
        _log(f"{user_key}: ОШИБКА генерации: {e} — возвращаю генерацию на баланс")
        db.add_credits(user_key, 1)  # не сгорела из-за нашей ошибки
        # Модерация модели (E005) — частый случай для портретов. Даём совет.
        if "sensitive" in str(e) or "E005" in str(e):
            channel.send_text(
                "😔 Нейросеть не смогла обработать это фото — система "
                "безопасности отклонила его.\n\n"
                "Попробуй другое селфи: где хорошо и чётко видно лицо, "
                "без других людей, в обычной одежде, при хорошем свете. "
                "Генерация возвращена на баланс 👍"
            )
        else:
            channel.send_text(
                "😔 Не получилось сгенерировать. Попробуй прислать фото ещё раз.\n"
                "Генерация возвращена на баланс 👍"
            )
        return
    _log(f"{user_key}: генерация ОК, {len(urls)} изображений")
    channel.send_photos(urls, "Готово! Твои фотосессии 🎨✨")
    channel.send_text(
        f"Нравится? 😍 Осталось {_balance_line(user_key)}.\n"
        "Пришли ещё фото — сделаю новую подборку!"
    )


def handle(user_key: str, channel) -> None:
    """Обработать одно входящее событие от пользователя."""
    incoming = channel.incoming
    text = (incoming.text or "").strip()

    sess_state = _sessions.get(user_key, {}).get("state", "<нет>")
    _log(f"{user_key}: handle state={sess_state} text={text!r}")

    # /start всегда сбрасывает диалог.
    if text.lower() in ("/start", "start", "начать", "старт"):
        _reset(user_key)
        greeting = GREETING + "\n\n" + _balance_greeting(user_key)
        channel.send_buttons(greeting, GENDER_OPTIONS)
        return

    sess = _session(user_key)

    # --- Кнопки оплаты работают в любом состоянии (payload ИЛИ подпись) ---
    plan_id = _parse_plan(text)
    if plan_id:
        _start_payment(user_key, plan_id, channel)
        return

    # Запасной путь: пользователь написал «я оплатил» текстом. Кнопки для
    # этого больше нет — подтверждение приходит автоматически через поллер.
    if text == "check_payment" or text.lower() in ("я оплатил", "оплатил"):
        _check_payments(user_key, channel)
        if db.has_generation(user_key):
            channel.send_text(payment_success_text(user_key))
            sess["state"] = S_PHOTO
        else:
            channel.send_text(
                "Пока не вижу оплату 🤔 Когда платёж пройдёт, я пришлю "
                "подтверждение автоматически — ждать осталось совсем чуть-чуть."
            )
        return

    state = sess["state"]

    if state == S_GENDER:
        gender = _parse_gender(text)
        if gender is None:
            channel.send_buttons(GREETING, GENDER_OPTIONS)
            return
        sess["gender"] = gender
        sess["state"] = S_PHOTO
        # Если баланса нет — сразу показываем тарифы, иначе просим фото.
        if db.has_generation(user_key):
            channel.send_text(ASK_PHOTO)
        else:
            channel.send_text("Чтобы начать, нужно оплатить тариф 👇")
            _show_paywall(user_key, channel)
        return

    if state == S_PHOTO:
        photo = incoming.photo_bytes()
        if not photo:
            _log(f"{user_key}: фото не распознано (text={text!r})")
            channel.send_text(
                "Жду фото 🙂 Пришли картинку — и я сделаю 4 креативные "
                "фотосессии."
            )
            return
        _run_generation(user_key, sess, photo, channel)
        return

    # Непредвиденное состояние — сброс.
    _reset(user_key)
    channel.send_buttons(GREETING, GENDER_OPTIONS)
