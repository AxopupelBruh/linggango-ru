"""Терпимое чтение JSON из модов.

Lang-файлы в сборке местами битые: BOM в начале, комментарии `//`,
висячие запятые, «невидимые» управляющие символы. Обычный json.loads
на них падает, и целый мод выпадает из перевода. Здесь — разбор с очисткой.
"""
from __future__ import annotations

import json
import re


def _strip_comments(text: str) -> str:
    """Убирает // и /* */ комментарии, не трогая содержимое строк."""
    out = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                j = text.find("\n", i)
                if j < 0:
                    break
                i = j
                continue
            if nxt == "*":
                j = text.find("*/", i + 2)
                i = n if j < 0 else j + 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    """Убирает запятые перед } или ]."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


RE_MISSING_COMMA = re.compile(
    r'("(?:[^"\\]|\\.)*")(\s*\r?\n\s*)("(?:[^"\\]|\\.)*"\s*:)')


def _add_missing_commas(text: str) -> str:
    """Ставит запятую между записями, где мод её потерял."""
    return RE_MISSING_COMMA.sub(r"\1,\2\3", text)


def load_lang_json(raw: bytes | str) -> dict:
    """Читает lang-файл мода. Бросает ValueError, если это не JSON."""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = raw.lstrip("﻿")
    text = _strip_comments(text)
    text = _strip_trailing_commas(text)
    text = _add_missing_commas(text)
    data = json.loads(text, strict=False)
    if not isinstance(data, dict):
        raise ValueError("lang-файл не является объектом")
    return data
