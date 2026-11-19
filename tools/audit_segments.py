"""Сегментный аудит переводов квестов: ищем пропавшие слова и мусор.

Идея: обе строки (EN и RU) режем по тегам на сегменты. Если в EN-сегменте есть
текст, а в соответствующем RU-сегменте его нет или он подозрительно короткий —
значит, при перестройке фразы модель что-то потеряла.

Признаки мусора в RU:
  * « , » / « . » — пропавшее слово перед знаком препинания;
  * два пробела подряд;
  * латиница, склеенная с кириллицей;
  * пустой RU-сегмент при непустом EN-сегменте.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

RE_TAG = re.compile(r"(</?[^>]+>)")
RE_COLOR = re.compile(r"[§&](?:[0-9a-fk-orA-FK-OR]|x)")
RE_GLUE = re.compile(r"[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]")
RE_WORD = re.compile(r"[A-Za-zА-Яа-яЁё][\w'’-]*")
RE_DANGLING = re.compile(r"\s+([,.!?;:])")
RE_DOUBLE = re.compile(r"  +")


def segments(text: str) -> list[str]:
    """Текстовые куски между тегами (теги не входят)."""
    parts = RE_TAG.split(text)
    # нечётные индексы — текст, чётные — теги
    return [parts[i] for i in range(0, len(parts), 2)]


def words(t: str) -> list[str]:
    return RE_WORD.findall(RE_COLOR.sub(" ", t))


def main() -> None:
    ru = json.loads((WORK / "quests_ru.json").read_text(encoding="utf-8"))
    en_index = json.loads((WORK / "quests.json").read_text(encoding="utf-8"))

    empty_seg: list[str] = []
    short_seg: list[str] = []
    dangling: list[str] = []
    glue: list[str] = []

    for en, ru_text in ru.items():
        if not ru_text:
            continue
        loc = en_index.get(en, ["?"])[0]
        r = RE_COLOR.sub(" ", ru_text)

        if RE_GLUE.search(r):
            glue.append(loc)
        if RE_DANGLING.search(r) or RE_DOUBLE.search(r):
            dangling.append(loc)

        es, rs = segments(en), segments(ru_text)
        if len(es) != len(rs):
            continue
        for a, b in zip(es, rs):
            aw, bw = words(a), words(b)
            if aw and not bw:
                empty_seg.append(loc)
                break
            if len(aw) >= 4 and len(bw) < len(aw) * 0.35:
                short_seg.append(loc)
                break

    def show(name: str, items: list[str]) -> None:
        print(f"\n=== {name}: {len(items)}")
        for i in items:
            print("  ", i)

    show("пустой RU-сегмент при непустом EN", sorted(set(empty_seg)))
    show("RU-сегмент сильно короче EN", sorted(set(short_seg)))
    show("висячая пунктуация / двойные пробелы", sorted(set(dangling)))
    show("склейка кириллицы и латиницы", sorted(set(glue)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
