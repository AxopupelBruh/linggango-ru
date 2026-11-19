"""Разбор текстовых полей в файлах FTB Quests (SNBT).

В FTB Quests описание квеста — это СПИСОК строк:
    description: [
        "первая строка"
        "вторая строка"
    ]
а заголовок — одиночная строка. Раньше мы брали только одиночные строки,
поэтому 4655 блоков описаний остались нетронутыми.

Здесь общий разбор: и сбор строк, и подстановка переводов.
"""
from __future__ import annotations

import re

# поля, в которых лежит видимый игроку текст
SCALAR_KEYS = ("title", "subtitle", "description", "objective", "name")
BLOCK_KEYS = ("description", "subtitle", "hover", "objectives", "hints")

RE_SCALAR = re.compile(
    r'^(?P<indent>\s*)(?P<key>' + "|".join(SCALAR_KEYS) + r'):\s*"(?P<text>(?:[^"\\]|\\.)*)"\s*$')
RE_BLOCK_START = re.compile(
    r'^(?P<indent>\s*)(?P<key>' + "|".join(BLOCK_KEYS) + r'):\s*\[\s*$')
RE_BLOCK_INLINE = re.compile(
    r'^(?P<indent>\s*)(?P<key>' + "|".join(BLOCK_KEYS) + r'):\s*\[(?P<rest>.*)\]\s*$')
RE_ITEM = re.compile(r'"(?P<text>(?:[^"\\]|\\.)*)"')
# поля внутри строки: { id: "X", title: "WIP" }
RE_INLINE_SCALAR = re.compile(
    r'(?P<pre>[\{,]\s*)(?P<key>title|subtitle|description):\s*"(?P<text>(?:[^"\\]|\\.)*)"')


def unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\\\", "\\")


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def iter_texts(raw: str):
    """Отдаёт все текстовые строки файла: (ключ, текст, начало, конец).

    начало/конец — смещения в исходном тексте, чтобы можно было заменить
    строку на месте, не трогая остальную структуру.
    """
    lines = raw.split("\n")
    offset = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        m = RE_SCALAR.match(line)
        if m:
            text = m.group("text")
            start = offset + m.start("text")
            end = offset + m.end("text")
            yield m.group("key"), unescape(text), start, end
            offset += len(line) + 1
            i += 1
            continue

        m = RE_BLOCK_INLINE.match(line)
        if m:
            # однострочный список: description: ["строка1" "строка2"]
            key = m.group("key")
            base = offset + m.start("rest")
            for im in RE_ITEM.finditer(m.group("rest")):
                yield key, unescape(im.group("text")), base + im.start("text"), base + im.end("text")
            offset += len(line) + 1
            i += 1
            continue

        m = RE_BLOCK_START.match(line)
        if m:
            key = m.group("key")
            # собираем блок до закрывающей скобки; pos — абсолютное смещение
            # начала текущей строки (важно: элементы блока идут на разных строках)
            j = i + 1
            pos = offset + len(line) + 1
            items = []
            while j < len(lines):
                if lines[j].strip().startswith("]"):
                    break
                for im in RE_ITEM.finditer(lines[j]):
                    items.append((pos + im.start("text"), pos + im.end("text"),
                                  unescape(im.group("text"))))
                pos += len(lines[j]) + 1
                j += 1
            for s, e, text in items:
                yield key, text, s, e
            # смещение до конца блока
            consumed = 0
            for k in range(i, min(j + 1, len(lines))):
                consumed += len(lines[k]) + 1
            offset += consumed
            i = j + 1
            continue

        # заголовок/описание прямо в строке: { id: "X", title: "WIP" }
        if "title:" in line or "description:" in line or "subtitle:" in line:
            for im in RE_INLINE_SCALAR.finditer(line):
                start = offset + im.start("text")
                end = offset + im.end("text")
                yield im.group("key"), unescape(im.group("text")), start, end

        offset += len(line) + 1
        i += 1


def collect(raw: str) -> list[str]:
    """Все уникальные текстовые строки файла."""
    seen = []
    known = set()
    for _key, text, _s, _e in iter_texts(raw):
        if text not in known:
            known.add(text)
            seen.append(text)
    return seen


def replace(raw: str, translations: dict[str, str]) -> tuple[str, int, int]:
    """Заменяет тексты на переводы. Возвращает (новый текст, заменено, всего)."""
    edits = []
    total = 0
    for _key, text, start, end in iter_texts(raw):
        total += 1
        ru = translations.get(text)
        if ru and ru != text:
            edits.append((start, end, escape(ru)))
    if not edits:
        return raw, 0, total
    # применяем с конца, чтобы смещения не «поехали»
    edits.sort(key=lambda e: e[0], reverse=True)
    out = raw
    for start, end, replacement in edits:
        out = out[:start] + replacement + out[end:]
    return out, len(edits), total
