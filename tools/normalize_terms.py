"""Нормализация терминологии во всём переводе.

Источники истины:
  * ванильная русская локализация 1.20.1 (ru_ru из ассетов);
  * решения по игровым терминам пака (Looting = Грабеж, Slate = сланец …).

Правила:
  GLOBAL    — замена везде, регистр сохраняется;
  CONTEXT   — замена только в строках, где в английском есть термин
               (иначе можно испортить другие значения слов);
  PAIRS     — замена по конкретной паре ключ→значение.

Запуск:  python normalize_terms.py [--dry]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
SOURCES = ("quests_ru", "mods_ru", "kubejs_ru", "patchouli_ru")

# --- глобальные замены: (что было, как надо) -------------------------------
GLOBAL: list[tuple[str, str]] = [
    ("Скулк", "Скалк"),                 # ваниль: Скалковый сенсор
    ("Надкрылья", "Элитры"),            # ваниль: Элитры
    ("Диспенсер", "Раздатчик"),         # ваниль: Раздатчик
    ("Прочность брони", "Твёрдость брони"),   # ваниль: armor_toughness
    ("Кальмар", "Спрут"),               # ваниль: Спрут
    ("Копье", "Копьё"),
    ("Руби", "Рубин"),
    ("Медлительность", "Замедление"),   # ваниль: Замедление
    ("Галена", "Галенит"),
    ("Олимпус", "Олимп"),
    ("Путевой камень", "Путеводный камень"),
    ("Зеленый", "Зелётый"),
    ("Шелк", "Шёлк"),
    ("Мед", "Мёд"),
    ("Уитер", "Визер"),                 # ваниль: Визер
    ("Уизера", "Визера"),
    ("Челендж", "Вызов"),
    ("челендж", "вызов"),
    ("Крестик Божественности", "Крест Божественности"),
]

# --- замены в зависимости от английского оригинала -----------------------
CONTEXT: list[tuple[str, str, str]] = [
    ("phase", "Ступень", "Фаза"),
    ("phase", "ступень", "фаза"),
    ("fortune", "Фортуна", "Удача"),
    ("fortune", "фортуна", "удача"),
    ("knockback", "Отдача", "Отбрасывание"),
    ("knockback", "отдача", "отбрасывание"),
    ("attack damage", "Урон от атаки", "Урон при атаке"),
    ("attack damage", "урон от атаки", "урон при атаке"),
    ("magic damage", "Магический урон", "Заклинательный урон"),
    ("magic damage", "магический урон", "заклинательный урон"),
    ("buff", "Шлифование", "Бафф"),
    ("buff", "шлифование", "бафф"),
    ("daemonium", "Демонит", "Демониум"),
    ("daemonium", "демонит", "демониум"),
    ("daemonium", "демония", "демониума"),
    ("slate", "Укреплённый грифельный", "Армированный сланец"),
    ("slate", "Демоническая доска", "Демонический сланец"),
    ("slate", "Демоническая‌ доска", "Демонический сланец"),
    ("slate", "грифельный", "сланец"),
    ("slate", "Грифельный", "Сланец"),
    ("slate", "доска", "сланец"),
    ("slate", "Чистый лист", "Пустой сланец"),
    ("slate", "чистый лист", "пустой сланец"),
    ("slate", "Чистые листы", "Пустые сланцы"),
    ("slate", "чистые листы", "пустые сланцы"),
    ("slate", "Демоническая доска", "Демонический сланец"),
]

# --- замены внутри составных слов (по вхождению, с учётом оригинала) ------
CONTEXT_SUBSTR: list[tuple[str, str, str]] = [
    ("sculk", "Скулк", "Скалк"),
    ("sculk", "скулк", "скалк"),
]

# --- точечные замены по паре ключ→значение ---------------------------------
PAIRS: dict[str, dict[str, str]] = {
    "mods_ru": {
        "Deepslate Brick Chimney": "Кирпичный дымоход из глубинного сланца",
        "Cobbled Deepslate Chimney": "Дымоход из брусчатки глубинного сланца",
        "Polished Deepslate Chimney": "Дымоход из полированного глубинного сланца",
        "Deepslate Tile Chimney": "Дымоход из плитки глубинного сланца",
        "Deepslate Frame": "Рамка из глубинного сланца",
        "Deepslate Sarcophagus": "Саркофаг из глубинного сланца",
        "Deepslate Slab": "Плита из глубинного сланца",
        "Deepslate Worldroot Ore": "Руда корня мира из глубинного сланца",
        "Deepslate Zenalite Ore": "Зеналитовая руда из глубинного сланца",
        "Slate Ampoule": "Ампула сланца",
        "Slate-infused Vial": "Флакон, наполненный сланцем",
        "A glass vial infused with a simple slate.":
            "Стеклянный флакон, настоянный на простом сланце.",
        "Blank Slate": "Пустой сланец",
        "Blank Slates": "Пустые сланцы",
        "Reinforced Slate": "Армированный сланец",
        "Imbued Slate": "Пропитанный сланец",
        "Demonic Slate": "Демонический сланец",
        "Ethereal Slate": "Эфирный сланец",
        "§6Blank Sanguine Scroll§r\nUses Blank Slate\n50 uses\n\n§cLP Cost:§r Base x Spell Level\nCommon: 2,000 | Uncommon: 4,000\nRare: 8,000 | Epic: 12,000\nLegendary: 16,000":
            "§6Пустой сангвинический свиток§r\nИспользует пустой сланец\n50 применений\n\n§cСтоимость LP:§r базовый x уровень заклинания\nОбычный: 2 000 | Необычный: 4 000\nРедкий: 8 000 | Эпический: 12 000\nЛегендарный: 16 000",
        "§6Reinforced Sanguine Scroll§r\nUses Reinforced Slate\n100 uses\n\n§cLP Cost:§r Base x Spell Level\nCommon: 2,000 | Uncommon: 4,000\nRare: 8,000 | Epic: 12,000\nLegendary: 16,000":
            "§6Армированный сангвинический свиток§r\nИспользует армированный сланец\n100 применений\n\n§cСтоимость LP:§r базовый x уровень заклинания\nОбычный: 2 000 | Необычный: 4 000\nРедкий: 8 000 | Эпический: 12 000\nЛегендарный: 16 000",
        "§6Imbued Sanguine Scroll§r\nUses Imbued Slate\n200 uses\n\n§cLP Cost:§r Base x Spell Level\nCommon: 2,000 | Uncommon: 4,000\nRare: 8,000 | Epic: 12,000\nLegendary: 16,000":
            "§6Пропитанный сангвинический свиток§r\nИспользует пропитанный сланец\n200 применений\n\n§cСтоимость LP:§r базовый x уровень заклинания\nОбычный: 2 000 | Необычный: 4 000\nРедкий: 8 000 | Эпический: 12 000\nЛегендарный: 16 000",
    },
    "quests_ru": {
        "Blank Slates": "Пустые сланцы",
        "Reinforced Slate": "Армированный сланец",
        "Imbued Slate": "Пропитанный сланец",
        "Demonic Slate": "Демонический сланец",
        "Ethereal Slate": "Эфирный сланец",
    },
}


def match_case(src: str, canon: str) -> str:
    if src.isupper() and len(src) > 1:
        return canon.upper()
    if src[:1].isupper():
        return canon[:1].upper() + canon[1:]
    return canon


def sub_word(text: str, old: str, new: str) -> tuple[str, int]:
    """Замена с учётом границ слова, регистр сохраняется."""
    pattern = re.compile(r"(?<![A-Za-zА-Яа-яЁё])" + re.escape(old) + r"(?![A-Za-zА-Яа-яЁё])")
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return match_case(m.group(0), new)

    return pattern.sub(repl, text), n


def main() -> None:
    dry = "--dry" in sys.argv
    total = 0
    for src_name in SOURCES:
        p = WORK / f"{src_name}.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        changed = 0
        # 1. точечные пары
        for en, ru in PAIRS.get(src_name, {}).items():
            if en in data and data[en] != ru:
                data[en] = ru
                changed += 1
                print(f"  [{src_name}] пара: {en[:50]!r} -> {ru[:50]!r}")
        # 2. глобальные замены
        for old, new in GLOBAL:
            for en in list(data):
                ru = data[en]
                if not isinstance(ru, str) or old not in ru:
                    continue
                ru2, n = sub_word(ru, old, new)
                if n:
                    data[en] = ru2
                    changed += 1
        # 3. контекстные замены внутри составных слов
        for term, old, new in CONTEXT_SUBSTR:
            for en in list(data):
                ru = data[en]
                if not isinstance(ru, str) or old not in ru:
                    continue
                if term.lower() not in en.lower():
                    continue
                data[en] = ru.replace(old, new)
                changed += 1
        # 4. контекстные замены
        for term, old, new in CONTEXT:
            for en in list(data):
                ru = data[en]
                if not isinstance(ru, str) or old not in ru:
                    continue
                if term.lower() not in en.lower():
                    continue
                ru2, n = sub_word(ru, old, new)
                if n:
                    data[en] = ru2
                    changed += 1
        print(f"[{src_name}] изменено строк: {changed}")
        total += changed
        if not dry:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"всего изменено строк: {total}")


if __name__ == "__main__":
    main()
