"""Правки регистра и брендов в карте перевода (work/mods_ru.json).

Что чинит:
  1. Перевод начинается с маленькой буквы, а оригинал — с большой.
     В русском предложение и имя начинаются с большой буквы, поэтому
     «Persistence» → «настойчивость» превращается в «Настойчивость».
     Учитываем ведущие коды цвета (§9), разметку и пробелы.
  2. Транслитерации брендов: «ФТБ» → «FTB», «ДЖЭИ» → «JEI», «РЕЙ» → «REI».
     Названия модов остаются на английском.
  3. Перевод, полностью совпадающий с оригиналом, — трогаем только если
     это заведомо мусор (единицы измерения вида «mB» → «МБ»).

Запуск:
    python fix_case.py            # показать, что поменяется
    python fix_case.py --apply    # применить
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
MODS_RU = WORK / "mods_ru.json"

# бренды чинит audit_case.py (brands.restore_brands) — здесь не дублируем

# ведущие коды цвета / разметка, за которыми ищем первую букву
LEAD = re.compile(r"^(\s*(?:[§&][0-9a-fk-orA-FK-OR]|\[[^\]]{0,40}\]|<[^>]{0,40}>)*)")
CYR = re.compile(r"[а-яёА-ЯЁ]")


def cap_first(text: str) -> str:
    """Капитализирует первую букву слова, не трогая разметку.

    Правила:
      * капитализируем, только если строка начинается именно с буквы
        («жидкость» → «Жидкость»);
      * если впереди плейсхолдер («%s должна быть…») — не поднимаем: это
        слово не в начале фразы;
      * если впереди число («60 секунд», «+1.5 к дальности») — не поднимаем:
        это продолжение числового обозначения, а не начало предложения.
    """
    m = LEAD.match(text)
    lead = m.group(1) if m else ""
    rest = text[len(lead):]
    cm = CYR.search(rest)
    if not cm:
        return text
    i = cm.start()
    prefix = rest[:i]
    if re.search(r"%[-+0-9.#]*[a-zA-Z]|\{\d+\}|\{|\d", prefix):
        return text
    return lead + rest[:i] + rest[i].upper() + rest[i + 1:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    issues = json.loads((WORK / "case_issues.json").read_text(encoding="utf-8"))
    mods = json.loads(MODS_RU.read_text(encoding="utf-8"))

    changes: list[dict] = []
    for it in issues:
        en, ru = it["en"], it["ru"]
        if it["kind"] == "brand":
            new = it.get("fixed") or ru
            if new != ru:
                changes.append({"en": en, "old": ru, "new": new, "kind": "brand"})
        elif it["kind"] == "lower_start":
            new = cap_first(ru)
            if new != ru:
                changes.append({"en": en, "old": ru, "new": new, "kind": "cap"})

    # единицы измерения и прочие мелочи — отдельным точечным списком
    UNITS = {"mB": "мБ", "MB": "МБ", "kB": "кБ", "KB": "КБ", "GB": "ГБ", "TB": "ТБ"}
    for it in issues:
        if it["kind"] == "upper_start" and it["en"].strip() in UNITS:
            en = it["en"]
            if en in mods and mods[en] != UNITS[en]:
                changes.append({"en": en, "old": mods[en], "new": UNITS[en], "kind": "unit"})

    print(f"изменений: {len(changes)}")
    for c in changes[:25]:
        print(f"  [{c['kind']}] {c['en'][:44]!r}")
        print(f"        {c['old'][:46]!r} -> {c['new'][:46]!r}")
    if len(changes) > 25:
        print(f"  ... ещё {len(changes) - 25}")

    (WORK / "case_changes.json").write_text(
        json.dumps(changes, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.apply:
        for c in changes:
            if c["en"] in mods:
                mods[c["en"]] = c["new"]
        MODS_RU.write_text(json.dumps(mods, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"применено в {MODS_RU.name}: {len(changes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
