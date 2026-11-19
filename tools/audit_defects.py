"""Финальный аудит дефектов перевода квестов.

Проверки:
  1. структура тегов EN != RU — модель потеряла или переставила блок разметки;
  2. склейка кириллицы и латиницы («emp ты», «снiffer'ом»);
  3. латиница в RU, которой нет в EN (незакрытые английские слова);
  4. висячая пунктуация (« , », « . ») — пропало слово перед знаком;
  5. двойные пробелы внутри слова.

Цветовые коды (&e, §c) и теги убираются ДО проверок, чтобы не давать ложных срабатываний.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

RE_TAG = re.compile(r"</?[^>]+>")
RE_COLOR = re.compile(r"[§&](?:[0-9a-fk-orA-FK-OR]|x)")
RE_GLUE = re.compile(r"[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]")
RE_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
RE_DANGLING = re.compile(r"[ \t]+([,.!?;:])")
RE_DOUBLE = re.compile(r"\S  +\S")
RE_ZWNJ = "‌"


def prep(text: str) -> str:
    return RE_COLOR.sub("", RE_TAG.sub(" ", text))


def main() -> None:
    ru = json.loads((WORK / "quests_ru.json").read_text(encoding="utf-8"))
    en_index = json.loads((WORK / "quests.json").read_text(encoding="utf-8"))

    struct: list[str] = []
    glue: list[str] = []
    latin: list[str] = []
    dangle: list[str] = []
    doubles: list[str] = []

    for en, ru_text in ru.items():
        if not ru_text:
            continue
        loc = en_index.get(en, ["?"])[0]

        if RE_TAG.findall(en) != RE_TAG.findall(ru_text):
            struct.append(loc)

        p = prep(ru_text)
        if RE_GLUE.search(p):
            glue.append(loc)
        if RE_DANGLING.search(p):
            dangle.append(loc)
        if RE_DOUBLE.search(p):
            doubles.append(loc)

        ew = {w.lower() for w in RE_WORD.findall(prep(en))}
        extra = [w for w in RE_WORD.findall(p) if w.lower() not in ew]
        if extra:
            latin.append(f"{loc} :: {', '.join(extra)}")

    def show(name: str, items: list[str]) -> None:
        print(f"\n=== {name}: {len(items)}")
        for i in items:
            print("  ", i)

    show("структура тегов не совпала", sorted(set(struct)))
    show("склейка кириллицы и латиницы", sorted(set(glue)))
    show("висячая пунктуация", sorted(set(dangle)))
    show("двойные пробелы", sorted(set(doubles)))
    show("латиница, которой нет в EN", latin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
