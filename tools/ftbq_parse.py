"""Разбор файла FTB Quests на квесты: {id: [тексты]}.

Разбирает блоки квестов (отступ ``\\t\\t{`` … ``\\t\\t}``) и внутри каждого
берёт поля title / subtitle / description / objective / name / hover,
которые видны игроку.
"""
from __future__ import annotations

import re

RE_BLOCK_START = re.compile(r"^\t\t\{\s*$")
RE_BLOCK_END = re.compile(r"^\t\t\}\s*$")
RE_QID = re.compile(r'^\t\t\tid:\s*"([0-9A-Fa-f]{8,})"')
RE_SCALAR = re.compile(r'^\t\t\t(\w+):\s*"((?:[^"\\]|\\.)*)"\s*$')
RE_ARRAY_OPEN = re.compile(r"^\t\t\t(\w+):\s*\[\s*$")
RE_ARRAY_INLINE = re.compile(r'^\t\t\t(\w+):\s*\[(.*)\]\s*$')
RE_ITEM = re.compile(r'"((?:[^"\\]|\\.)*)"')

SCALARS = ("title", "subtitle", "description", "objective", "name")
ARRAYS = ("description", "subtitle", "hover", "objectives", "hints")


def unescape(t: str) -> str:
    return t.replace('\\"', '"').replace("\\\\", "\\")


def parse_file(raw: str) -> dict[str, list[str]]:
    """{id квеста: [тексты в порядке появления]}"""
    lines = raw.split("\n")
    out: dict[str, list[str]] = {}
    i = 0
    while i < len(lines):
        if not RE_BLOCK_START.match(lines[i]):
            i += 1
            continue
        j = i + 1
        block = []
        while j < len(lines) and not RE_BLOCK_END.match(lines[j]):
            block.append(lines[j])
            j += 1
        qid = None
        texts: list[str] = []
        k = 0
        while k < len(block):
            line = block[k]
            if qid is None:
                m = RE_QID.match(line)
                if m:
                    qid = m.group(1)
            m = RE_SCALAR.match(line)
            if m and m.group(1) in SCALARS:
                texts.append(unescape(m.group(2)))
                k += 1
                continue
            m = RE_ARRAY_INLINE.match(line)
            if m and m.group(1) in ARRAYS:
                for im in RE_ITEM.finditer(m.group(2)):
                    texts.append(unescape(im.group(1)))
                k += 1
                continue
            m = RE_ARRAY_OPEN.match(line)
            if m and m.group(1) in ARRAYS:
                k += 1
                while k < len(block) and not block[k].strip().startswith("]"):
                    for im in RE_ITEM.finditer(block[k]):
                        texts.append(unescape(im.group(1)))
                    k += 1
                k += 1
                continue
            k += 1
        if qid:
            out.setdefault(qid, []).extend(texts)
        i = j + 1
    return out
