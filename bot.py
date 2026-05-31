"""Бот нейрофотосессий для Telegram, ВКонтакте и MAX.

Диалог: пол -> оплата при необходимости -> фото -> генерация (Replicate gpt-image-2).
Вся логика разговора в dialog.py и не зависит от платформы; здесь — три
long-polling цикла и реализация «каналов» (отправка/приём для каждой сети).

Незаполненные в .env токены пропускаются. Запуск: python bot.py
"""

import json
import os
import re
import sys
import threading
import time
import traceback

import requests

import db
import dialog
import notifier
import payments

# --- .env ------------------------------------------------------------------

def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
VK_TOKEN = os.environ.get("VK_TOKEN", "").strip()
VK_GROUP_ID = os.environ.get("VK_GROUP_ID", "").strip()
MAX_TOKEN = os.environ.get("MAX_TOKEN", "").strip()

HTTP_TIMEOUT = 100


def log(platform: str, message: str) -> None:
    print(f"[{platform}] {message}", flush=True)


def fetch_bytes(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            return r.content
    except requests.RequestException:
        pass
    return None


# ===========================================================================
# Telegram
# ===========================================================================
# https://core.telegram.org/bots/api

class TelegramIncoming:
    def __init__(self, bot, message: dict):
        self.bot = bot
        self.message = message
        self.text = message.get("text") or message.get("caption") or ""

    def photo_bytes(self):
        photos = self.message.get("photo")
        if not photos:
            return None
        # Берём самый крупный размер (последний в массиве).
        file_id = photos[-1]["file_id"]
        info = self.bot.api("getFile", file_id=file_id)
        if not info.get("ok"):
            return None
        path = info["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{self.bot.token}/{path}"
        return fetch_bytes(url)


class TelegramChannel:
    def __init__(self, bot, chat_id: int, incoming: TelegramIncoming):
        self.bot = bot
        self.chat_id = chat_id
        self.incoming = incoming

    def send_text(self, text: str):
        self.bot.api("sendMessage", chat_id=self.chat_id, text=text)

    def _reply_keyboard(self, options, per_row: int):
        # options: list[(payload, label)]. У reply-кнопок payload = текст подписи,
        # поэтому шлём label; парсер в dialog.py распознаёт подписи.
        rows, row = [], []
        for _payload, label in options:
            row.append({"text": label})
            if len(row) == per_row:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return json.dumps({
            "keyboard": rows,
            "resize_keyboard": True,
            "one_time_keyboard": True,
        })

    def send_buttons(self, text: str, options):
        self.bot.api("sendMessage", chat_id=self.chat_id, text=text,
                     reply_markup=self._reply_keyboard(options, per_row=2))

    def send_styles_menu(self, text: str, options):
        self.bot.api("sendMessage", chat_id=self.chat_id, text=text,
                     reply_markup=self._reply_keyboard(options, per_row=2))

    def send_photos(self, urls, caption: str):
        if len(urls) == 1:
            self.bot.api("sendPhoto", chat_id=self.chat_id,
                         photo=urls[0], caption=caption)
            return
        media = []
        for i, u in enumerate(urls):
            item = {"type": "photo", "media": u}
            if i == 0:
                item["caption"] = caption
            media.append(item)
        self.bot.api("sendMediaGroup", chat_id=self.chat_id,
                     media=json.dumps(media))


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()

    def api(self, method: str, **params) -> dict:
        r = self.session.post(f"{self.base}/{method}", data=params,
                              timeout=HTTP_TIMEOUT)
        return r.json()

    def send_text_to(self, native_id: str, text: str):
        self.api("sendMessage", chat_id=native_id, text=text)

    def run(self):
        notifier.register("tg", self.send_text_to)
        offset = None
        log("Telegram", "запущен")
        while True:
            try:
                params = {"timeout": 60, "allowed_updates": '["message"]'}
                if offset is not None:
                    params["offset"] = offset
                data = self.session.get(f"{self.base}/getUpdates",
                                        params=params, timeout=HTTP_TIMEOUT).json()
                if not data.get("ok"):
                    log("Telegram", f"ошибка API: {data}")
                    time.sleep(3)
                    continue
                for upd in data["result"]:
                    offset = upd["update_id"] + 1
                    msg = upd.get("message")
                    if not msg:
                        continue
                    chat_id = msg["chat"]["id"]
                    kind = "фото" if msg.get("photo") else (
                        repr(msg.get("text") or msg.get("caption") or "?"))
                    log("Telegram", f"входящее от {chat_id}: {kind}")
                    incoming = TelegramIncoming(self, msg)
                    channel = TelegramChannel(self, chat_id, incoming)
                    self._safe_handle(f"tg:{chat_id}", channel)
            except requests.RequestException as e:
                log("Telegram", f"сетевая ошибка: {e}")
                time.sleep(3)

    def _safe_handle(self, key, channel):
        try:
            dialog.handle(key, channel)
        except Exception:  # noqa: BLE001 — не роняем цикл из-за одного юзера
            log("Telegram", f"ошибка обработки {key}:\n{traceback.format_exc()}")


# ===========================================================================
# ВКонтакте
# ===========================================================================
# https://dev.vk.com/ru/api/bots-long-poll/getting-started

VK_API_VERSION = "5.199"


class VkIncoming:
    def __init__(self, bot, message: dict):
        self.bot = bot
        self.message = message
        self.text = message.get("text") or ""

    def photo_bytes(self):
        for att in self.message.get("attachments", []):
            if att.get("type") != "photo":
                continue
            sizes = att["photo"].get("sizes", [])
            if not sizes:
                continue
            # Самый большой размер — максимальная площадь.
            best = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
            return fetch_bytes(best["url"])
        return None


class VkChannel:
    def __init__(self, bot, peer_id: int, incoming: VkIncoming):
        self.bot = bot
        self.peer_id = peer_id
        self.incoming = incoming

    def send_text(self, text: str):
        self.bot.send_message(self.peer_id, text)

    def _keyboard(self, options, per_row: int):
        # VK text-кнопка шлёт свой label как сообщение; payload кладём тоже,
        # но парсер dialog.py распознаёт и по подписи.
        rows, row = [], []
        for payload, label in options:
            row.append({
                "action": {
                    "type": "text",
                    "label": label[:40],
                    "payload": json.dumps({"p": payload}),
                },
                "color": "primary",
            })
            if len(row) == per_row:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return json.dumps({"one_time": True, "buttons": rows},
                          ensure_ascii=False)

    def send_buttons(self, text: str, options):
        self.bot.send_message(self.peer_id, text,
                              keyboard=self._keyboard(options, per_row=2))

    def send_styles_menu(self, text: str, options):
        self.bot.send_message(self.peer_id, text,
                              keyboard=self._keyboard(options, per_row=2))

    def send_photos(self, urls, caption: str):
        attachments = []
        for u in urls:
            data = fetch_bytes(u)
            if not data:
                continue
            att = self.bot.upload_photo(self.peer_id, data)
            if att:
                attachments.append(att)
        self.bot.send_message(self.peer_id, caption,
                              attachment=",".join(attachments) or None)


class VkBot:
    def __init__(self, token: str, group_id: str):
        self.token = token
        self.group_id = re.sub(r"\D", "", group_id)
        self.session = requests.Session()

    def api(self, method: str, **params) -> dict:
        params.update({"access_token": self.token, "v": VK_API_VERSION})
        r = self.session.post(f"https://api.vk.com/method/{method}",
                              data=params, timeout=HTTP_TIMEOUT)
        return r.json()

    _rand = int(time.time())

    def send_message(self, peer_id: int, text: str, attachment=None,
                     keyboard=None):
        VkBot._rand += 1
        params = {"peer_id": peer_id, "random_id": VkBot._rand}
        if text:
            params["message"] = text
        if attachment:
            params["attachment"] = attachment
        if keyboard:
            params["keyboard"] = keyboard
        res = self.api("messages.send", **params)
        if "error" in res:
            log("VK", f"messages.send: {res['error']}")

    def upload_photo(self, peer_id: int, image_bytes: bytes):
        """Загружает фото для отправки в ЛС, возвращает 'photo{owner}_{id}'."""
        srv = self.api("photos.getMessagesUploadServer", peer_id=peer_id)
        if "error" in srv:
            log("VK", f"getMessagesUploadServer: {srv['error']}")
            return None
        upload_url = srv["response"]["upload_url"]
        try:
            up = self.session.post(
                upload_url,
                files={"photo": ("photo.jpg", image_bytes, "image/jpeg")},
                timeout=HTTP_TIMEOUT,
            ).json()
        except requests.RequestException as e:
            log("VK", f"upload: {e}")
            return None
        saved = self.api("photos.saveMessagesPhoto",
                         photo=up.get("photo"), server=up.get("server"),
                         hash=up.get("hash"))
        if "error" in saved or not saved.get("response"):
            log("VK", f"saveMessagesPhoto: {saved.get('error')}")
            return None
        p = saved["response"][0]
        return f"photo{p['owner_id']}_{p['id']}"

    def send_text_to(self, native_id: str, text: str):
        self.send_message(int(native_id), text)

    def run(self):
        if not self.group_id:
            log("VK", "не указан числовой VK_GROUP_ID — платформа пропущена")
            return
        notifier.register("vk", self.send_text_to)
        log("VK", "запущен")
        while True:
            try:
                srv = self.api("groups.getLongPollServer", group_id=self.group_id)
                if "error" in srv:
                    log("VK", f"getLongPollServer: {srv['error']}")
                    time.sleep(5)
                    continue
                server = srv["response"]["server"]
                key = srv["response"]["key"]
                ts = srv["response"]["ts"]

                while True:
                    r = self.session.get(
                        server,
                        params={"act": "a_check", "key": key, "ts": ts, "wait": 25},
                        timeout=HTTP_TIMEOUT,
                    ).json()
                    if "failed" in r:
                        if r["failed"] == 1:
                            ts = r["ts"]
                            continue
                        break  # переполучить ключ/сервер
                    ts = r["ts"]
                    for event in r.get("updates", []):
                        if event.get("type") != "message_new":
                            continue
                        msg = event["object"]["message"]
                        peer_id = msg["peer_id"]
                        incoming = VkIncoming(self, msg)
                        channel = VkChannel(self, peer_id, incoming)
                        self._safe_handle(f"vk:{peer_id}", channel)
            except requests.RequestException as e:
                log("VK", f"сетевая ошибка: {e}")
                time.sleep(5)

    def _safe_handle(self, key, channel):
        try:
            dialog.handle(key, channel)
        except Exception as e:  # noqa: BLE001
            log("VK", f"ошибка обработки {key}: {e}")


# ===========================================================================
# MAX
# ===========================================================================
# https://dev.max.ru/docs-api — токен в заголовке Authorization.

class MaxIncoming:
    def __init__(self, bot, message: dict):
        self.bot = bot
        self.message = message
        body = message.get("body", {})
        self.text = body.get("text") or ""

    def photo_bytes(self):
        body = self.message.get("body", {})
        for att in body.get("attachments", []):
            if att.get("type") != "image":
                continue
            payload = att.get("payload", {})
            url = payload.get("url") or payload.get("token")
            if url and url.startswith("http"):
                return fetch_bytes(url)
        return None


class MaxChannel:
    def __init__(self, bot, chat_id, user_id, incoming: MaxIncoming):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
        self.incoming = incoming

    def _send_params(self):
        if self.chat_id is not None:
            return {"chat_id": self.chat_id}
        return {"user_id": self.user_id}

    def send_text(self, text: str):
        self.bot.send(self._send_params(), {"text": text})

    def _keyboard_attachment(self, options, per_row: int):
        rows, row = [], []
        for payload, label in options:
            row.append({"type": "callback", "text": label[:40],
                        "payload": payload})
            if len(row) == per_row:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return {"type": "inline_keyboard", "payload": {"buttons": rows}}

    def send_buttons(self, text: str, options):
        self.bot.send(self._send_params(), {
            "text": text,
            "attachments": [self._keyboard_attachment(options, per_row=2)],
        })

    def send_styles_menu(self, text: str, options):
        self.bot.send(self._send_params(), {
            "text": text,
            "attachments": [self._keyboard_attachment(options, per_row=2)],
        })

    def send_photos(self, urls, caption: str):
        # MAX требует загрузки изображения; используем upload flow.
        tokens = []
        for u in urls:
            data = fetch_bytes(u)
            if not data:
                continue
            tok = self.bot.upload_image(data)
            if tok:
                tokens.append(tok)
        if not tokens:
            self.send_text(caption + "\n(не удалось приложить изображения)")
            return
        attachments = [{"type": "image", "payload": {"token": t}} for t in tokens]
        self.bot.send(self._send_params(),
                      {"text": caption, "attachments": attachments})


class MaxBot:
    def __init__(self, token: str):
        self.token = token
        self.base = "https://platform-api.max.ru"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": token})

    def send(self, params: dict, body: dict):
        try:
            self.session.post(f"{self.base}/messages", params=params,
                              json=body, timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            log("MAX", f"send: {e}")

    def upload_image(self, image_bytes: bytes):
        """Получает URL загрузки изображения, заливает файл, возвращает token."""
        try:
            up = self.session.post(f"{self.base}/uploads",
                                   params={"type": "image"},
                                   timeout=HTTP_TIMEOUT).json()
            upload_url = up.get("url")
            if not upload_url:
                log("MAX", f"uploads: нет url ({up})")
                return None
            res = self.session.post(
                upload_url,
                files={"data": ("photo.jpg", image_bytes, "image/jpeg")},
                timeout=HTTP_TIMEOUT,
            ).json()
            # token может прийти на верхнем уровне или внутри photos.
            if "token" in res:
                return res["token"]
            photos = res.get("photos") or {}
            for v in photos.values():
                if isinstance(v, dict) and v.get("token"):
                    return v["token"]
            log("MAX", f"upload: токен не найден ({res})")
            return None
        except requests.RequestException as e:
            log("MAX", f"upload: {e}")
            return None

    def answer_callback(self, callback_id: str):
        """Подтверждает нажатие callback-кнопки (убирает «часики»)."""
        if not callback_id:
            return
        try:
            self.session.post(f"{self.base}/answers",
                              params={"callback_id": callback_id},
                              json={}, timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            log("MAX", f"answer: {e}")

    @staticmethod
    def _key(chat_id, user_id) -> str:
        # Сохраняем ТИП получателя в ключе: c<chat_id> или u<user_id>,
        # чтобы потом (в т.ч. из поллера платежей) уметь отправить ответ.
        if chat_id is not None:
            return f"max:c{chat_id}"
        return f"max:u{user_id}"

    def send_text_to(self, native_id: str, text: str):
        # native_id вида "c123" (chat_id) или "u456" (user_id).
        if native_id.startswith("c"):
            params = {"chat_id": native_id[1:]}
        elif native_id.startswith("u"):
            params = {"user_id": native_id[1:]}
        else:
            params = {"chat_id": native_id}
        self.send(params, {"text": text})

    def run(self):
        notifier.register("max", self.send_text_to)
        marker = None
        log("MAX", "запущен")
        while True:
            try:
                params = {"timeout": 90,
                          "types": "message_created,message_callback"}
                if marker is not None:
                    params["marker"] = marker
                data = self.session.get(f"{self.base}/updates", params=params,
                                        timeout=HTTP_TIMEOUT).json()
                marker = data.get("marker", marker)
                for upd in data.get("updates", []):
                    utype = upd.get("update_type")
                    if utype == "message_created":
                        self._on_message(upd.get("message", {}))
                    elif utype == "message_callback":
                        self._on_callback(upd)
            except requests.RequestException as e:
                log("MAX", f"сетевая ошибка: {e}")
                time.sleep(3)

    def _on_message(self, message: dict):
        recipient = message.get("recipient", {})
        chat_id = recipient.get("chat_id")
        user_id = recipient.get("user_id")
        incoming = MaxIncoming(self, message)
        channel = MaxChannel(self, chat_id, user_id, incoming)
        self._safe_handle(self._key(chat_id, user_id), channel)

    def _on_callback(self, upd: dict):
        callback = upd.get("callback", {})
        payload = callback.get("payload", "")
        callback_id = callback.get("callback_id") or callback.get("id")
        self.answer_callback(callback_id)

        # id чата/пользователя ищем в нескольких вероятных местах схемы.
        message = upd.get("message", {}) or callback.get("message", {})
        recipient = message.get("recipient", {})
        chat_id = recipient.get("chat_id")
        user = callback.get("user", {})
        user_id = recipient.get("user_id") or user.get("user_id")
        if chat_id is None and user_id is None:
            log("MAX", f"callback без получателя: {upd}")
            return

        # Превращаем нажатие в «текстовое» событие с payload — dialog его поймёт.
        incoming = MaxIncoming(self, {"body": {"text": payload}})
        channel = MaxChannel(self, chat_id, user_id, incoming)
        self._safe_handle(self._key(chat_id, user_id), channel)

    def _safe_handle(self, key, channel):
        try:
            dialog.handle(key, channel)
        except Exception as e:  # noqa: BLE001
            log("MAX", f"ошибка обработки {key}: {e}")


# ===========================================================================
# Точка входа
# ===========================================================================

def payment_poller():
    """Фоновый опрос ЮKassa: тихо начисляет оплаченные тарифы.

    Пользователь увидит зачисление автоматически в том мессенджере, где начал
    оплату. Для учебного проекта это проще, чем поднимать публичный webhook.
    """
    log("payments", "поллер запущен")
    while True:
        try:
            for p in db.pending_payments():
                try:
                    status = payments.get_status(p["payment_id"])
                except payments.PaymentError:
                    continue
                if status == "succeeded":
                    dialog._grant(p["user_key"], p["plan"])
                    db.mark_payment(p["payment_id"], "succeeded")
                    dialog.on_payment_succeeded(p["user_key"])
                    sent = notifier.notify(
                        p["user_key"], dialog.payment_success_text(p["user_key"]))
                    log("payments", f"зачислен {p['payment_id']} ({p['plan']}), "
                                    f"уведомление={'ок' if sent else 'не доставлено'}")
                elif status == "canceled":
                    db.mark_payment(p["payment_id"], "canceled")
        except Exception as e:  # noqa: BLE001
            log("payments", f"ошибка поллера: {e}")
        time.sleep(10)


def main():
    if not os.environ.get("REPLICATE_API_TOKEN", "").strip():
        log("main", "ВНИМАНИЕ: REPLICATE_API_TOKEN не задан — генерация работать не будет")

    db.init()
    if payments.is_configured():
        log("main", "ЮKassa настроена — приём оплаты включён")
        threading.Thread(target=payment_poller, name="payments", daemon=True).start()
    else:
        log("main", "ВНИМАНИЕ: ключи ЮKassa не заданы — оплата недоступна")

    platforms = []
    if TELEGRAM_TOKEN:
        platforms.append(("Telegram", TelegramBot(TELEGRAM_TOKEN).run))
    if VK_TOKEN:
        platforms.append(("VK", VkBot(VK_TOKEN, VK_GROUP_ID).run))
    if MAX_TOKEN:
        platforms.append(("MAX", MaxBot(MAX_TOKEN).run))

    if not platforms:
        sys.exit("Не задан ни один токен в .env — нечего запускать.")

    log("main", f"Запускаю платформы: {', '.join(n for n, _ in platforms)}")
    for name, target in platforms:
        threading.Thread(target=target, name=name, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("main", "Остановка по Ctrl+C")


if __name__ == "__main__":
    main()
