"""Чистка артефактов подстановки брендов в work/mods_ru.json.

Старая версия brands.py меняла подстроки, из-за чего обычные слова ломались:
  «Создайте скафандр» → «Createте скафандр»   (бренд Create + глагол)
  «Нефритный»        → «Jadeный»

Этот скрипт:
  1. откатывает такие артефакты;
  2. применяет корректный brands.restore_brands (только для брендов-имён);
  3. показывает, что изменилось.

Запуск:
    python3 cleanup_brands.py           # показать
    python3 cleanup_brands.py --apply   # применить
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
MODS_RU = WORK / "mods_ru.json"

sys.path.insert(0, str(HERE))
from brands import restore_brands  # noqa: E402

# откат старых (подстрочных) замен
REVERT = [
    ("Createте", "Создайте"),
    ("Createй", "Создай"),
    ("Createть", "Создать"),
    ("Createйте", "Создайте"),
    ("Jadeный", "Нефритный"),
    ("Jadeная", "Нефритная"),
    ("Jadeное", "Нефритное"),
    ("Jadeные", "Нефритные"),
    ("Jade", "Нефрит"),
    ("Создать", "Создать"),
]


def revert(text: str) -> str:
    for a, b in REVERT:
        if a != b:
            text = text.replace(a, b)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    mods = json.loads(MODS_RU.read_text(encoding="utf-8"))
    changes: list[tuple[str, str, str]] = []
    for en, ru in mods.items():
        if not isinstance(ru, str):
            continue
        new = revert(ru)
        new = restore_brands(en, new)
        if new != ru:
            changes.append((en, ru, new))

    print(f"изменений: {len(changes)}")
    for en, old, new in changes[:25]:
        print(f"  EN={en[:44]!r}\n     {old[:52]!r}\n  →  {new[:52]!r}")
    if len(changes) > 25:
        print(f"  ... ещё {len(changes) - 25}")

    if args.apply:
        for en, old, new in changes:
            mods[en] = new
        MODS_RU.write_text(json.dumps(mods, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"применено в {MODS_RU.name}: {len(changes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
