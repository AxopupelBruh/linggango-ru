"""Бэкенд перевода через DeepL API Free (api-free.deepl.com).

Ключи читаются из файла .deepl_keys (по одному в строке) или из переменной
DEEPL_API_KEY. Несколько ключей поддерживаются: при 429 берётся следующий.

§-коды Minecraft защищаются XML-тегами (DeepL tag_handling=xml) — так
цветовые коды не ломаются при переводе.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

URL = "https://api-free.deepl.com/v2/translate"
CODE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
XML = re.compile(r"<(/?)([a-zA-Z0-9_]+)(/?)>")


def mask_codes(text: str) -> tuple[str, list[str]]:
    """Заменяет §-коды на XML-теги, чтобы DeepL их не тронул."""
    codes: list[str] = []

    def repl(m: re.Match) -> str:
        codes.append(m.group(0))
        return f"<g{len(codes) - 1}/>"

    return CODE.sub(repl, text), codes


def unmask_codes(text: str, codes: list[str]) -> str:
    """Возвращает §-коды на место (DeepL сохраняет теги, но меняет их вид)."""
    def repl(m: re.Match) -> str:
        idx = m.group(1)
        if idx.isdigit() and int(idx) < len(codes):
            return codes[int(idx)]
        return m.group(0)

    return re.sub(r"<g(\d+)/>", repl, text)


CODE_RE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
WS = re.compile(r"^(\s*)(.*?)(\s*)$", re.S)


def split_by_codes(text: str) -> list[tuple[str, list[str]]]:
    """Делит строку на части между §-кодами.

    Возвращает список (текст, [коды перед ним]). Коды приклеиваются к тексту
    обратно после перевода, поэтому DeepL не сдвинет форматирование.
    """
    parts: list[tuple[str, list[str]]] = []
    codes: list[str] = []
    pos = 0
    for m in CODE_RE.finditer(text):
        chunk = text[pos:m.start()]
        # этот кусок идёт после ранее накопленных кодов
        parts.append((chunk, list(codes)))
        # текущий код открывает следующий кусок
        codes = [m.group(0)]
        pos = m.end()
    parts.append((text[pos:], list(codes)))
    return parts


def split_ws(text: str) -> tuple[str, str, str]:
    """Отделяет пробелы по краям — их переводить не нужно."""
    m = WS.match(text)
    if not m:
        return "", text, ""
    return m.group(1), m.group(2), m.group(3)


class DeepLBackend:
    name = "deepl"
    URL = URL
    max_items = 40

    def __init__(self, keys: list[str] | None = None, delay: float = 0.6,
                 target_lang: str = "RU"):
        if keys is None:
            keys = []
            env = os.environ.get("DEEPL_API_KEY", "").strip()
            if env:
                keys = [k.strip() for k in env.split(",") if k.strip()]
            f = HERE / ".deepl_keys"
            if f.exists():
                keys += [k.strip() for k in f.read_text(encoding="utf-8").splitlines() if k.strip()]
            if not keys:
                raise RuntimeError("deepl: нет ключей (DEEPL_API_KEY или .deepl_keys)")
        self.keys = list(dict.fromkeys(keys))
        self.delay = delay
        self.target_lang = target_lang
        self._lock = threading.Lock()
        self._last = 0.0
        self._key_idx = 0
        self.calls = 0
        self.quota_hits = 0

    def _throttle(self) -> None:
        with self._lock:
            gap = time.time() - self._last
            if gap < self.delay:
                time.sleep(self.delay - gap)
            self._last = time.time()

    def _post(self, payload: dict) -> dict:
        import requests
        last = ""
        for attempt in range(5):
            key = self.keys[self._key_idx % len(self.keys)]
            try:
                self._throttle()
                r = requests.post(
                    self.URL,
                    headers={"Authorization": f"DeepL-Auth-Key {key}",
                             "Content-Type": "application/json"},
                    data=json.dumps(payload).encode("utf-8"),
                    timeout=90,
                )
                self.calls += 1
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 456):
                    # 429 — лимит запросов, 456 — исчерпан лимит символов:
                    # в обоих случаях берём следующий ключ
                    self.quota_hits += 1
                    self._key_idx += 1
                    if self._key_idx >= len(self.keys) * 2:
                        raise RuntimeError("deepl: все ключи исчерпали лимит")
                    time.sleep(2)
                    continue
                if r.status_code in (400, 403):
                    raise RuntimeError(f"deepl: HTTP {r.status_code}: {r.text[:200]}")
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(3 * (attempt + 1))
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"deepl: {last}")

    def translate(self, texts: list[str]) -> list[str]:
        """Переводит список строк, сохраняя §-коды и их позиции."""
        if not texts:
            return []
        # 1. режем по §-кодам и по краям пробелов
        jobs: list[tuple[str, str, str]] = []     # (lead, core, trail)
        layout: list[list[tuple[int, str]]] = []  # для каждой исходной строки
        for text in texts:
            row: list[tuple[int, str]] = []
            for chunk, _codes in split_by_codes(text):
                lead, core, trail = split_ws(chunk)
                row.append((len(jobs), lead))
                jobs.append((lead, core, trail))
            layout.append(row)

        cores = [c for _l, c, _t in jobs]
        cores = [c for c in cores if c.strip()]
        translated: dict[str, str] = {}
        if cores:
            uniq = list(dict.fromkeys(cores))
            for i in range(0, len(uniq), self.max_items):
                batch = uniq[i:i + self.max_items]
                payload = {
                    "text": batch,
                    "target_lang": self.target_lang,
                    "source_lang": "EN",
                    "preserve_formatting": True,
                }
                data = self._post(payload)
                for src, tr in zip(batch, data.get("translations", [])):
                    translated[src] = tr.get("text", "")
        # 2. склеиваем обратно: перевод + исходные пробелы + §-коды
        out: list[str] = []
        for text, row in zip(texts, layout):
            parts = split_by_codes(text)
            res = []
            for (idx, lead), (chunk, codes) in zip(row, parts):
                _l, core, _t = split_ws(chunk)
                ru = translated.get(core, core) if core.strip() else core
                res.append(lead + ru)
            # коды вставляем на свои места
            full = ""
            for (idx, _lead), (chunk, codes) in zip(row, parts):
                full += "".join(codes)
                _l, core, _t = split_ws(chunk)
                ru = translated.get(core, core) if core.strip() else core
                full += ru
            out.append(full)
        return out
