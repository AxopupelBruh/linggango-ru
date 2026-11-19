"""Узкий детектор дефектных переводов квестов.

Класс дефекта: модель перестраивала фразу и оставляла в RU английские слова
(«и emp ты», «b oss», «a баннер») — обычно при этом часть EN-слов терялась.

Ищем:
  1) RU с английскими словами, которых нет в EN как отдельных терминов;
  2) RU, где «английское» слово стоит рядом с кириллицей без разделителя
     (склейка: «emp ты», «b oss»);
  3) RU с пустым/мусорным сегментом между тегами.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

RE_TAG = re.compile(r"</?[^>]+>")
RE_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
RE_CYR = re.compile(r"[А-Яа-яЁё]")
# цветовые коды Minecraft (&e, §c, &x&f&f…) — не текст
RE_COLOR = re.compile(r"[§&](?:[0-9a-fk-orA-FK-OR]|x)")
# склейка латиницы с кириллицей без пробела
RE_GLUE = re.compile(r"[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]")


def clean(text: str) -> str:
    return RE_COLOR.sub(" ", text)


def words(text: str) -> list[str]:
    return RE_WORD.findall(RE_TAG.sub(" ", text))


def main() -> None:
    ru = json.loads((WORK / "quests_ru.json").read_text(encoding="utf-8"))
    en_index = json.loads((WORK / "quests.json").read_text(encoding="utf-8"))

    glue: list[str] = []
    mixed: list[str] = []
    for en, ru_text in ru.items():
        r = clean(ru_text)
        if RE_GLUE.search(r):
            glue.append(en)
        # латиница в RU, которой нет в EN
        ew = {w.lower() for w in words(en)}
        rw = [w for w in words(r) if w.lower() not in ew]
        if rw:
            mixed.append(en)

    print(f"RU с латиницей, которой нет в EN: {len(mixed)}")
    print(f"RU со склейкой кириллицы и латиницы: {len(glue)}")
    for en in glue:
        print("  ", en_index.get(en, ["?"])[0], "::", ru[en][:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
