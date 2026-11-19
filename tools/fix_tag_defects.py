"""Системная починка дефектов разметки в переводах квестов.

Найдено при аудите:
  * модель переводила названия тегов (<shake> → <встряхивание>), ломая рендер;
  * в параметрах тегов ставила запятые вместо точек (a=0,3 вместо a=0.3);
  * внутрь тегов попадал невидимый разделитель U+200C;
  * в текст просачивались служебные маркеры <x_N/>.

Скрипт чинит теги по EN-эталону: названия, десятичные точки, ZWNJ.
Текст между тегами не трогает — только разметку.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

RE_TAG = re.compile(r"<[^>]*>")
RE_NUM_COMMA = re.compile(r"([a-zA-Z]+)=(\d+),(\d+)")
ZWNJ = "‌"

# русские названия тегов → английские
TAG_RU2EN = {
    "глюк": "glitch",
    "сбой": "glitch",
    "дрожание": "shake",
    "встряхивание": "shake",
    "встряхиваться": "shake",
    "импульс": "pulse",
    "затухание": "fade",
    "отскок": "bounce",
    "турбо": "turb",
    "неон": "neon",
    "градиент": "grad",
    "тень": "shadow",
    "волна": "wave",
    "наклон": "tilt",
    "маятник": "swing",
    "подвеска": "pend",
    "дребезг": "glitch",
    "мерцание": "flicker",
    "радуга": "rainbow",
    "переход": "transition",
    "дожим": "squeeze",
    "пульс": "pulse",
    "прыжок": "bounce",
    "дрожание2": "shake",
}


def fix_tag(tag: str) -> str:
    """Чинит один тег: имя, десятичные точки, ZWNJ."""
    if not tag.startswith("<") or not tag.endswith(">"):
        return tag
    inner = tag[1:-1]
    closing = inner.startswith("/")
    if closing:
        inner = inner[1:]
    selfclose = inner.endswith("/")
    if selfclose:
        inner = inner[:-1]
    parts = inner.split(None, 1)
    name = parts[0]
    attrs = parts[1] if len(parts) > 1 else ""
    name = TAG_RU2EN.get(name.lower(), name)
    attrs = RE_NUM_COMMA.sub(r"\1=\2.\3", attrs)
    attrs = attrs.replace(ZWNJ, "")
    out = ("/" if closing else "") + name
    if attrs:
        out += " " + attrs
    if selfclose:
        out += "/"
    return "<" + out + ">"


def fix_tags(text: str) -> str:
    return RE_TAG.sub(lambda m: fix_tag(m.group(0)), text)


def main() -> None:
    p = WORK / "quests_ru.json"
    ru = json.loads(p.read_text(encoding="utf-8"))

    changed_tags = 0
    changed_garbage = 0
    still_diff = []

    for en, ru_text in list(ru.items()):
        if not ru_text:
            continue
        new = fix_tags(ru_text)
        if new != ru_text:
            changed_tags += 1
            ru[en] = new

    p.write_text(json.dumps(ru, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"исправлено строк с тегами: {changed_tags}")

    # контроль: мусорные маркеры и несовпадение структуры
    for en, ru_text in ru.items():
        if re.search(r"<[^>]*x_?\s*\d+/>", ru_text):
            changed_garbage += 1
        if RE_TAG.findall(en) != RE_TAG.findall(ru_text):
            still_diff.append(en)

    print(f"осталось строк с мусором <x_N/>: {changed_garbage}")
    print(f"строк, где структура тегов всё ещё не совпадает с EN: {len(still_diff)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
