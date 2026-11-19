"""Раунд 3: правки, которые не находятся по ключу, а ищутся по значению.

  * названия клавиш в тексте (Shift / Ctrl вместо «сдвиг»);
  * «Сдвиг сингулярности» — имя способности приводим к канону из lang-файла мода.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"


def load(name):
    p = WORK / f"{name}.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# (что ищем в значении, на что меняем)
MODS_VALUE_FIXES = [
    ("-Удерживайте сдвиг, чтобы получить дополнительную информацию-",
     "-Удерживайте Shift, чтобы получить дополнительную информацию-"),
    ("§7Удерживайте правую кнопку мыши + сдвиг в течение 0,5 секунды",
     "§7Удерживайте правую кнопку мыши + Shift в течение 0,5 секунды"),
    ("§6При нажатии правой кнопки мыши при сдвиге:",
     "§6По нажатию ПКМ с удержанием Shift:"),
    ("Включить перетаскивание при сдвиге",
     "Включить перетаскивание с Shift"),
    ("CTRL", "Ctrl"),
]

QUESTS_VALUE_FIXES = [
    ("Сингулярность\u200c Сдвиг", "Сдвиг сингулярности"),
]


def apply_value_fixes(src: str, fixes) -> int:
    p, data = load(src)
    n = 0
    for en, ru in data.items():
        if not isinstance(ru, str):
            continue
        new = ru
        for old, repl in fixes:
            if old == "CTRL":
                # только как отдельное слово
                new = new.replace(" CTRL ", " Ctrl ").replace("(CTRL", "(Ctrl")
                new = new.replace("CTRL +", "Ctrl +").replace("+CTRL", "+Ctrl")
                if new == "CTRL":
                    new = "Ctrl"
            else:
                new = new.replace(old, repl)
        if new != ru:
            data[en] = new
            n += 1
    save(p, data)
    return n


def main() -> None:
    total = 0
    n = apply_value_fixes("mods_ru", MODS_VALUE_FIXES)
    print(f"mods: значений исправлено {n}")
    total += n
    n = apply_value_fixes("quests_ru", QUESTS_VALUE_FIXES)
    print(f"quests: значений исправлено {n}")
    total += n
    print(f"всего: {total}")


if __name__ == "__main__":
    main()
