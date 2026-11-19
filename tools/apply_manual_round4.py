"""Раунд 4: точечные правки по смыслу (не по правилам перевода).

  * экран смерти Goety: «Weak to» → «Слаб к» (было «Слабый к»);
  * названия модификаторов сложности, которые машинный перевод исказил;
  * «Weakened Pick» (Blood Magic) → «Ослабленная кирка»;
  * имя пака остаётся английским: «Линганго» → «Linggango».
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"


def load(name):
    p = WORK / f"{name}.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# --- правки по ключу (EN → RU) -----------------------------------------
MODS_KEY_FIXES = {
    # экран смерти / аффинити
    "Weak to": "Слаб к",
    "Weak:": "Слаб к:",
    # Blood Magic: замедление копания
    "Weakened Pick": "Ослабленная кирка",
    # модификаторы сложности
    "Weak Mending": "Ослабленная починка",
    "Weak Lifter": "Слабый грузчик",
    "Spell Fizzle": "Сбой заклинания",
    "Backlash": "Отдача маны",
    "Lean Drops": "Скудные дропы",
    "Restless": "Беспокойный",
    "Brawler": "Драчун",
    "Broke": "Разорительный",
    "Seasoned": "Закалённый",
    "Drought": "Засуха",
    "Monster Mash": "Мясорубка",
    "No Turtling": "Нет черепашки",
    "No Warps": "Нет варпов",
}


def apply_key_fixes(name, fixes) -> int:
    p, data = load(name)
    n = 0
    for en, ru in fixes.items():
        if en in data and data[en] != ru:
            data[en] = ru
            n += 1
    save(p, data)
    return n


# --- правки по значению (во всех наборах) ------------------------------
RX_PACK = re.compile(r"\bЛинганго\b")


def apply_pack_name() -> int:
    total = 0
    for name in ("quests_ru", "mods_ru", "extra_ru", "kubejs_ru", "patchouli_ru"):
        p, data = load(name)
        n = 0
        for en, ru in data.items():
            if not isinstance(ru, str) or "Линганго" not in ru:
                continue
            new = RX_PACK.sub("Linggango", ru)
            if new != ru:
                data[en] = new
                n += 1
        save(p, data)
        print(f"{name}: «Линганго» → «Linggango» в {n} строках")
        total += n
    return total


def main() -> None:
    n = apply_key_fixes("mods_ru", MODS_KEY_FIXES)
    print(f"mods: ключей исправлено {n}")
    n2 = apply_pack_name()
    print(f"всего строк с правкой имени пака: {n2}")


if __name__ == "__main__":
    main()
