"""Слияние с переводом k1n1maro/-Linggango + починка терминов.

Что делаем:
  1. В квестах — точечная замена сломанных мест в нашем переводе
     (текст берём свой, сохраняя разметку и ZWNJ-разбивку,
      слова — из проверенного чужого перевода, где он лучше).
  2. В lang-файлах модов — единый термин «Slate → сланец»
     (глоссарий тащил «грифельный» из темы Jade).

Ключи ищем по нормализованному английскому (без ZWNJ), чтобы не ошибиться
в невидимых символах.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"

ZWNJ = "‌"


def norm(s: str) -> str:
    return s.replace(ZWNJ, "").replace("‌", "")


# ---------------------------------------------------------------------------
# 1. Квесты: (нормализованный EN, [(старый фрагмент, новый фрагмент)])
# ---------------------------------------------------------------------------

QUEST_FIXES: list[tuple[str, list[tuple[str, str]]]] = [
    ("To start collecting some Source, we'll need a Source Jar.",
     [("некоторые исходные файлы", "Источник"),
      ("архив исходных файлов", "сосуд Источника")]),
    ("The amount of source varies per potion and complexity.",
     [("исходного вещества", "источника")]),
    ("Crafting that runs on Demon Will",
     [("на Demon Будет", "на Демонической воле")]),
    ("Reinforced Slate plus 5,000 LP at Tier 3",
     [("грифельный", "сланец")]),
    ("Imbued Slate plus 15,000 LP at Tier 4",
     [("грифельный", "сланец")]),
    ("[!success] If you are wearing the `Ring of the Seven Curses`, this is the point where LP stops being what limits your spellcasting.",
     [("Кольцо семи семи проклятий`", "`Кольцо семи проклятий`")]),
    ("[!tip] 108 runes is 108 Blank Slates. If you got here without a `Well of Suffering` or an `Incense Altar`, go back and build one, it is not worth doing this by hand.",
     [("пустых дощеток", "пустых сланцев"),
      ("Алтаря ,", "Алтаря благовоний,")]),
    ("Recommended to spawn the wither at least one thousand&r blocks away from your base.",
     [("размещать Уизера", "призывать Иссушителя")]),
    ("&8The leader of the &6&lNether Cult&r&8, the king of the &0&lBottomless Pit...&4&l Apollyon.&r&8 It is your task to challenge him and hopefully overcome his wickedness and free this world of his influence.",
     [("Ваша челендж", "Ваша задача")]),
    ("This is what a viking would eat",
     [("Вот что викинг ел бы", "Вот что ел бы викинг")]),
    ("You'll need many to build the outer shell, forming the structural base for fuel rods.",
     [("Вам понадобится от до для изготовления внешней оболочки",
       "Вам понадобится много таких, чтобы изготовить внешнюю оболочку")]),
    ("Super stove for delights!",
     [("Супер-кухонная кухонная плита", "Супер-печь")]),
    ("Reduces the required aureal depending on the time of day.",
     [("требуемую площадь", "требуемую ауреаль")]),
    ("A witch's classic",
     [("Классический от ведьмы", "Классика ведьмы")]),
    ("Can be used on &epets&r and &eSheeps&r to un wash them.",
     [("чтобы от их мыть", "чтобы отмыть их")]),
    ("Can be placed in a pile of up to 8.",
     [("в стопку от до 8", "стопкой до 8 штук")]),
    ("Pretty intuitive to use, you just power one and it will power its adjacent cogs, up to 14 blocks away, just like with &aRedstone Dust&r.",
     [("Довольно интуитивно понятное использование для", "Довольно интуитивно понятен в использовании"),
      ("соседние винтики, от до 14 блоков", "соседние винтики на расстоянии до 14 блоков")]),
    ("Can be renamed in an &aAnvil&r to change the name that will be displayed in chat. Rename it \"\" to get rid of it completely.",
     [("в &aНаковальне&r на изменить", "в &aНаковальне&r, чтобы изменить"),
      ("чтобы полностью избавиться от", "чтобы полностью от него избавиться")]),
    ("Once powered it will initiate a rotation action which will take time depending on the signal strength it is receiving.",
     [("Как только он будет включен инициирует действие вращения, которое займет время в зависимости от мощности сигнала который он принимает",
       "Как только он будет включён, он инициирует вращение, которое займёт время в зависимости от мощности принимаемого сигнала")]),
    ("The dark powers help you in your fights and protect you from incoming damage.",
     [("помогают тебе в сражениях и защищают тебя от наносимого урона",
       "помогают вам в сражениях и защищают вас от входящего урона")]),
    ("&cThe Ancient Remnant&r survived that one meteor, is that enough?",
     [("&cТот древний остаток&r, который пережил тот единственный метеорит, — этого достаточно?",
       "&cДревний остаток&r пережил тот единственный метеорит — этого достаточно?")]),
    ("Horizontal ropes do have a hitbox and can be walked on,",
     [("и по можно ходить", "и по ним можно ходить")]),
    ("Also prevent the crop from being trampled.",
     [("Также предотвратите урожай от вытаптывания", "Также предотвращает вытаптывание урожая")]),
    ("The text resolution that is getting displayed depends on the amount of text in a page. Add whitespaces to make it render smaller.",
     [("Разрешение текста, при котором отображается, зависит от количества текста на странице. Добавьте пробелы в и сделайте меньше",
       "Разрешение отображаемого текста зависит от количества текста на странице. Добавьте пробелы, чтобы сделать его меньше")]),
    ("Once an item is taken or removed from a pedestal the block will give out a observer detectable update.",
     [("Как только предмет будет взят или удален с пьедестала блок выдаст обновление, обнаруживаемое наблюдателем",
       "Как только предмет будет взят или удалён с пьедестала, блок выдаст обновление, обнаруживаемое наблюдателем")]),
    ("Take away the things you don't like in life.,",
     [("в жизни.,", "в жизни.")]),
    ("OHh.. this one too", [("Ой... этот тоже", "Ох.. и этот тоже")]),
    (" The Abacus will count up to 48 blocks, drawing an outline of the counted blocks. The texture of the item will change according to how many blocks are counted. Right-click again to unbind.",
     [("Абак будут подсчитывать", "Счёты будут подсчитывать"),
      ("Текстура элемента изменится", "Текстура предмета изменится"),
      ("количества блоков подсчитано", "количества подсчитанных блоков")]),
]

# ---------------------------------------------------------------------------
# 1б. Квесты: строки, которые проще переписать целиком
# ---------------------------------------------------------------------------

FULL_FIXES: dict[str, str] = {
    "Recommended to spawn the wither at least one thousand&r blocks away from your base.":
        "Рекомендуется‌ призывать Визера‌ на расстоянии не менее‌ одной‌ тысячи&r блоков‌ от‌ вашей‌ базы.",
    "Horizontal ropes do have a hitbox and can be walked on,":
        "Горизонтальные‌ веревки имеют‌ хитбокс‌, и по ним можно ходить,",
    "Can be renamed in an &aAnvil&r to change the name that will be displayed in chat. Rename it \"\" to get rid of it completely.":
        "Можно‌ переименовать‌ в &aНаковальне&r, чтобы изменить имя‌, которое будет отображаться‌ в чате. Переименуйте‌ его в \"\", чтобы полностью от него избавиться.",
    "Pretty intuitive to use, you just power one and it will power its adjacent cogs, up to 14 blocks away, just like with &aRedstone Dust&r. ":
        "Довольно интуитивно понятен в использовании: вы‌ просто включаете‌ один, и он‌ приводит в действие соседние винтики на расстоянии до 14 блоков, как и с &aRedstone‌ Dust&r. ",
    "Once powered it will initiate a rotation action which will take time depending on the signal strength it is receiving.":
        "Как только‌ он будет включён, он инициирует‌ вращение‌, которое займёт‌ время в зависимости от‌ мощности принимаемого сигнала.",
    "&cThe Ancient Remnant&r survived that one meteor, is that enough?":
        "&cДревний остаток&r пережил тот единственный метеорит — этого достаточно?",
    "The text resolution that is getting displayed depends on the amount of text in a page. Add whitespaces to make it render smaller.":
        "Разрешение‌ отображаемого‌ текста‌ зависит от‌ количества‌ текста‌ на‌ странице‌. Добавьте пробелы, чтобы сделать его меньше.",
    "Once an item is taken or removed from a pedestal the block will give out a observer detectable update.":
        "Как только‌ предмет‌ будет взят‌ или удалён с‌ пьедестала, блок‌ выдаст‌ обновление, обнаруживаемое наблюдателем.",
    "The Abacus will count up to 48 blocks, drawing an outline of the counted blocks. The texture of the item will change according to how many blocks are counted. Right-click again to unbind.":
        "Абак‌ будет‌ подсчитывать‌ до‌ 48 блоков, рисуя‌ контур‌ из‌ подсчитанных блоков. Текстура‌ предмета‌ изменится‌ в зависимости от‌ количества подсчитанных‌ блоков. Щелкните правой кнопкой мыши ещё раз, чтобы отменить привязку.",
    "OHh.. this one too": "Ох.. и этот тоже",
    "You’ll need many to build the outer shell, forming the structural base for fuel rods.":
        "Вам понадобится много таких, чтобы изготовить‌ внешнюю‌ оболочку, которая станет‌ несущей‌ основой для топливных‌ стержней.",
}

# ---------------------------------------------------------------------------
# 2. Моды: единый термин Slate → сланец, Deepslate → глубинный сланец
# ---------------------------------------------------------------------------

MOD_FIXES: dict[str, str] = {
    "Blank Slate": "Пустой сланец",
    "Reinforced Slate": "Армированный сланец",
    "Imbued Slate": "Пропитанный сланец",
    "Slate Ampoule": "Ампула сланца",
    "Slate-infused Vial": "Флакон, наполненный сланцем",
    "A glass vial infused with a simple slate.":
        "Стеклянный флакон, настоянный на простом сланце.",
    "Deepslate Brick Chimney": "Кирпичный дымоход из глубинного сланца",
    "Cobbled Deepslate Chimney": "Дымоход из брусчатки глубинного сланца",
    "Polished Deepslate Chimney": "Дымоход из полированного глубинного сланца",
    "Deepslate Tile Chimney": "Дымоход из плитки глубинного сланца",
    "Deepslate Frame": "Рамка из глубинного сланца",
    "Deepslate Sarcophagus": "Саркофаг из глубинного сланца",
    "Deepslate Slab": "Плита из глубинного сланца",
    "Deepslate Worldroot Ore": "Руда корня мира из глубинного сланца",
    "Deepslate Zenalite Ore": "Зеналитовая руда из глубинного сланца",
}


def load(name):
    p = WORK / f"{name}.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


RE_TOKEN = re.compile(r"‌|[^‌\s]+")


def split_chunks(val: str) -> list[list[str]]:
    """[ [слово, разделитель_после], ... ] — ZWNJ остаётся внутри слова."""
    parts = re.split(r"(\s+)", val)
    out: list[list[str]] = []
    for i in range(0, len(parts), 2):
        out.append([parts[i], parts[i + 1] if i + 1 < len(parts) else ""])
    return out


def join_chunks(chunks: list[list[str]]) -> str:
    return "".join(c[0] + c[1] for c in chunks)


def replace_words(val: str, old: str, new: str) -> str | None:
    """Заменяет фразу «old» на «new», сохраняя ZWNJ-разбивку и пробелы."""
    old_words = old.split(" ")
    new_words = new.split(" ")
    chunks = split_chunks(val)
    # индексы chunk'ов, где есть слово (chunk из одного ZWNJ — это разделитель)
    word_slots = [i for i, c in enumerate(chunks) if c[0].strip(ZWNJ)]
    slot_words = [chunks[i][0].strip(ZWNJ) for i in word_slots]

    for start in range(len(word_slots) - len(old_words) + 1):
        matched_slots = word_slots[start:start + len(old_words)]
        matched_words = slot_words[start:start + len(old_words)]
        ok = True
        for cw, ow in zip(matched_words, old_words):
            if not (cw.lower() == ow.lower() or cw.lower().startswith(ow.lower())):
                ok = False
                break
        if not ok:
            continue
        flags = [chunks[s][0].endswith(ZWNJ) for s in matched_slots]
        last_chunk = chunks[matched_slots[-1]][0].replace(ZWNJ, "")
        suffix = last_chunk[len(old_words[-1]):] if last_chunk.lower().startswith(
            old_words[-1].lower()) else ""
        last_sep = chunks[matched_slots[-1]][1]

        new_chunks: list[list[str]] = []
        for k, nw in enumerate(new_words):
            z = ZWNJ if flags[min(k, len(flags) - 1)] else ""
            sep = chunks[matched_slots[min(k, len(matched_slots) - 1)]][1] \
                if k < len(new_words) - 1 else last_sep
            if sep == "" and k < len(new_words) - 1:
                sep = " "
            new_chunks.append([nw + z, sep])
        new_chunks[-1][0] += suffix

        result = chunks[:matched_slots[0]] + new_chunks + chunks[matched_slots[-1] + 1:]
        return join_chunks(result)
    return None


def apply_quests() -> int:
    p, data = load("quests_ru")
    index = {norm(k): k for k in data}
    changed = 0
    for en, reps in QUEST_FIXES:
        key = index.get(norm(en))
        if key is None:
            print(f"  ! не найден ключ: {en[:70]}")
            continue
        val = data[key]
        new = val
        for old, rep in reps:
            got = replace_words(new, norm(old), norm(rep))
            if got is None:
                print(f"  ! фрагмент не найден в «{en[:40]}»: {old!r}")
                continue
            new = got
        if new != val:
            data[key] = new
            changed += 1

    # целиком переписанные строки
    for en, ru in FULL_FIXES.items():
        key = index.get(norm(en))
        if key is None:
            print(f"  ! не найден ключ (full): {en[:70]}")
            continue
        if data[key] != ru:
            data[key] = ru
            changed += 1
    save(p, data)
    return changed


def apply_mods() -> int:
    p, data = load("mods_ru")
    changed = 0
    for en, ru in MOD_FIXES.items():
        if en in data and data[en] != ru:
            data[en] = ru
            changed += 1
        elif en not in data:
            print(f"  ! нет ключа в модах: {en}")
    save(p, data)
    return changed


def main() -> None:
    n = apply_quests()
    print(f"квесты: исправлено строк {n}")
    m = apply_mods()
    print(f"моды: исправлено строк {m}")


if __name__ == "__main__":
    main()
