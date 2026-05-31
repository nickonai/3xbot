"""Генерация нейрофотосессии через Replicate (openai/gpt-image-2).

Работаем напрямую по REST API Replicate, без SDK. Входное фото пользователя
передаём как data URL (фото небольшие, до ~256 КБ обычно укладываемся, но и
крупнее проходит). На выходе — список URL сгенерированных изображений.
"""

import base64
import io
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

MODEL = "openai/gpt-image-2"
API = "https://api.replicate.com/v1"

# Сколько кадров в фотосессии и предельное время ожидания одной генерации.
IMAGES_PER_SHOOT = 4
POLL_TIMEOUT_SEC = 240
POLL_INTERVAL_SEC = 2


class GenerationError(Exception):
    """Понятная пользователю ошибка генерации."""


# Ограничиваем длинную сторону входного фото — крупные снимки раздувают
# data URL и замедляют загрузку, а для референса лица это избыточно.
MAX_INPUT_SIDE = 1280


def _normalize(image_bytes: bytes) -> bytes:
    """По возможности ужимает фото до разумного размера (JPEG)."""
    if not _HAS_PIL:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        if max(img.size) > MAX_INPUT_SIDE:
            img.thumbnail((MAX_INPUT_SIDE, MAX_INPUT_SIDE))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except Exception:
        return image_bytes  # не смогли обработать — шлём как есть


def _data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _token() -> str:
    # Читаем токен при вызове, а не на этапе импорта: к этому моменту .env
    # уже загружен в окружение (импорт модуля может произойти раньше load_env).
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        raise GenerationError("REPLICATE_API_TOKEN не задан")
    return token


def _generate_one(image_data_url: str, prompt: str, token: str) -> str:
    """Генерирует ОДНО изображение и возвращает его URL. Бросает GenerationError."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "input_images": [image_data_url],
            "number_of_images": 1,
            "aspect_ratio": "2:3",      # вертикаль — естественно для портрета
            "quality": "high",
            "output_format": "jpeg",
            # "low" — менее строгая модерация (gpt-image-2 часто помечает
            # обычные портреты как sensitive при "auto"). См. ошибку E005.
            "moderation": "low",
        }
    }
    try:
        # Prefer: wait — дать модели шанс отдать результат синхронно за ~60с.
        r = requests.post(
            f"{API}/models/{MODEL}/predictions",
            json=payload,
            headers={**headers, "Prefer": "wait"},
            timeout=90,
        )
    except requests.RequestException as e:
        raise GenerationError(f"сеть Replicate недоступна: {e}") from e

    # 200/201 — создано; 202 — принято и выполняется (дождёмся опросом).
    if r.status_code not in (200, 201, 202):
        raise GenerationError(f"Replicate вернул {r.status_code}: {r.text[:300]}")

    pred = _wait_until_done(r.json(), headers)
    output = pred.get("output")
    if not output:
        raise GenerationError("модель не вернула изображений")
    if isinstance(output, list):
        return output[0]
    return output


def generate_parallel(image_bytes: bytes, prompts: list[str]) -> list[str]:
    """Параллельно генерирует по одному кадру на каждый промпт.

    Возвращает список URL в порядке промптов (упавшие — пропускаются).
    Бросает GenerationError только если не удалось получить НИ одного кадра.
    """
    token = _token()
    image_data_url = _data_url(_normalize(image_bytes))

    results: list[str | None] = [None] * len(prompts)
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(prompts) or 1) as pool:
        futures = {
            pool.submit(_generate_one, image_data_url, p, token): i
            for i, p in enumerate(prompts)
        }
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except GenerationError as e:
                errors.append(str(e))

    urls = [u for u in results if u]
    if not urls:
        raise GenerationError("; ".join(errors) or "не удалось сгенерировать")
    return urls


def _wait_until_done(pred: dict, headers: dict) -> dict:
    """Опрашивает prediction, пока не достигнет терминального статуса."""
    elapsed = 0
    get_url = pred.get("urls", {}).get("get")

    while True:
        status = pred.get("status")
        if status == "succeeded":
            return pred
        if status in ("failed", "canceled"):
            raise GenerationError(
                f"генерация {status}: {pred.get('error') or 'без деталей'}"
            )

        if elapsed >= POLL_TIMEOUT_SEC:
            raise GenerationError("превышено время ожидания генерации")
        if not get_url:
            raise GenerationError("нет URL для опроса статуса prediction")

        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC
        try:
            resp = requests.get(get_url, headers=headers, timeout=30)
            pred = resp.json()
        except requests.RequestException as e:
            raise GenerationError(f"ошибка опроса статуса: {e}") from e
