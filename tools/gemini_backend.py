"""Бэкенд перевода через Gemini API (Google AI Studio, free tier).

Интерфейс совпадает с GoogleBackend/DeepLBackend из tr_engine:
    translate_batch(lines: list[str]) -> list[str]
Возвращает столько же строк, сколько было на входе.

Ключ берётся из GEMINI_API_KEY или из файла .gemini_key рядом со скриптом.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

SYSTEM_RULES = """Ты — профессиональный переводчик игровых локализаций (Minecraft-моды, предметы, зачарования, интерфейс).

Правила:
1. Переводи английский на русский. Стиль — естественный игровой русский, без машинной кальки.
2. СТРОГО сохраняй без изменений: плейсхолдеры (%s, %d, %1$s, %.2f, {0}, {}), коды цвета (§a, &c), числа, единицы измерения, URL, идентификаторы вида minecraft:stone, команды (/give), имена файлов.
3. НЕ переводи: названия модов и бренды (FTB, JEI, REI, WTHIT, Create, Mekanism, Ars Nouveau, Curios, Jade, Xaero's, Immersive Engineering, Sophisticated Storage, Occultism, Ad Astra и любые другие названия модов), имена игроков и персонажей, если это имя собственное.
4. Регистр сохраняй по образцу: Title Case → Title Case; обычное предложение с маленькой буквы → с маленькой буквы. Имена предметов, боссов и зачарований (как в оригинале с большой буквы) переводи с большой буквы.
5. Зачарования в квадратных скобках (например §4[Blood Drain]) переводи внутри скобок, квадратные скобки и коды цвета оставь как есть.
6. Ничего не добавляй, не комментируй, не сокращай.
7. Если строка — просто символы, числа или форматирование без слов, верни её без изменений."""

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.M)


class GeminiBackend:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    max_items = 100
    max_chars = 24000

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.1-flash-lite",
                 delay: float = 1.5, temperature: float = 0.15,
                 thinking_budget: int | None = None):
        key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            key_file = HERE / ".gemini_key"
            if key_file.exists():
                key = key_file.read_text(encoding="utf-8").strip()
        if not key:
            raise RuntimeError("gemini: нет ключа (GEMINI_API_KEY или .gemini_key)")
        self.api_key = key
        self.model = model
        self.delay = delay
        self.temperature = temperature
        self.thinking_budget = thinking_budget
        self._lock = threading.Lock()
        self._last = 0.0
        self.calls = 0
        self.input_chars = 0
        self.output_chars = 0

    def _throttle(self) -> None:
        with self._lock:
            gap = time.time() - self._last
            if gap < self.delay:
                time.sleep(self.delay - gap)
            self._last = time.time()

    def _prompt(self, lines: list[str]) -> str:
        payload = json.dumps(lines, ensure_ascii=False)
        return (
            f"{SYSTEM_RULES}\n\n"
            f"Верни ТОЛЬКО JSON-массив из {len(lines)} переводов в том же порядке, "
            f"что исходные строки (каждый перевод — строка JSON).\n"
            f"Исходные строки:\n{payload}"
        )

    def _extract_text(self, data: dict) -> str:
        """Достаёт текст ответа, пропуская thinking-части."""
        parts = data["candidates"][0]["content"].get("parts", [])
        chunks = [p.get("text", "") for p in parts
                  if p.get("text") and not p.get("thought")]
        if not chunks:
            chunks = [p.get("text", "") for p in parts if p.get("text")]
        return "".join(chunks)

    def _parse(self, text: str, n: int) -> list[str]:
        raw = text.strip()
        raw = _FENCE.sub("", raw).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("["), raw.rfind("]")
            if start < 0 or end <= start:
                raise RuntimeError(f"gemini: не разобрал JSON: {raw[:200]}")
            data = json.loads(raw[start:end + 1])
        if not isinstance(data, list) or len(data) != n:
            raise RuntimeError(f"gemini: ожидалось {n} строк, получено "
                               f"{len(data) if isinstance(data, list) else 'не список'}")
        return [str(x) for x in data]

    def _request(self, lines: list[str]) -> list[str]:
        import requests

        body = {
            "contents": [{"role": "user", "parts": [{"text": self._prompt(lines)}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
                "maxOutputTokens": 16384,
            },
        }
        if self.thinking_budget is not None:
            body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": self.thinking_budget}
        last = ""
        for attempt in range(6):
            try:
                self._throttle()
                r = requests.post(
                    self.URL.format(model=self.model),
                    headers={"x-goog-api-key": self.api_key,
                             "Content-Type": "application/json"},
                    data=json.dumps(body).encode("utf-8"),
                    timeout=180,
                )
                self.calls += 1
                if r.status_code == 200:
                    data = r.json()
                    text = self._extract_text(data)
                    self.input_chars += len(self._prompt(lines))
                    self.output_chars += len(text)
                    return self._parse(text, len(lines))
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 403, 404):
                    # ошибка запроса — повтор не поможет
                    raise RuntimeError(f"gemini: {last}")
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(min(60, 8 * (attempt + 1)) + random.uniform(0, 3))
                    continue
                raise RuntimeError(f"gemini: {last}")
            except RuntimeError:
                if attempt == 5:
                    raise
                time.sleep(5 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
                if attempt == 5:
                    raise RuntimeError(f"gemini: {last}") from exc
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"gemini: {last}")

    def translate_batch(self, lines: list[str]) -> list[str]:
        if not lines:
            return []
        if len(lines) <= self.max_items and sum(len(x) for x in lines) <= self.max_chars:
            return self._request(lines)
        # режем на куски
        out: list[str] = []
        chunk: list[str] = []
        size = 0
        for ln in lines:
            if chunk and (len(chunk) >= self.max_items or size + len(ln) > self.max_chars):
                out.extend(self._request(chunk))
                chunk, size = [], 0
            chunk.append(ln)
            size += len(ln)
        if chunk:
            out.extend(self._request(chunk))
        return out
