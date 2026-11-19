"""Переводит lang-файлы KubeJS и добавляет блок ru_ru в client_scripts/lang.js.

KubeJS-ресурсы имеют приоритет над обычными ресурспаками, поэтому русские
файлы пишем прямо в kubejs/assets/<ns>/lang/ru_ru.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).parent
ROOT = INSTANCE
WORK = HERE / "work"
LANG_JS = ROOT / "kubejs/client_scripts/lang.js"

# названия из client_scripts/lang.js — их нет в lang-файлах, переводим вручную
LANGJS_NAMES = {
    "Linggango Journal": "Журнал Лингганго",
    "Zenalite Ore": "Зеналитовая руда",
    "Concentrated Bronze Helmet": "Шлем из концентрированной бронзы",
    "Concentrated Bronze Chestplate": "Нагрудник из концентрированной бронзы",
    "Concentrated Bronze Leggings": "Поножи из концентрированной бронзы",
    "Concentrated Bronze Boots": "Сапоги из концентрированной бронзы",
    "Concentrated Bronze Sword": "Меч из концентрированной бронзы",
    "Concentrated Bronze Pickaxe": "Кирка из концентрированной бронзы",
    "Concentrated Bronze Axe": "Топор из концентрированной бронзы",
    "Concentrated Bronze Shovel": "Лопата из концентрированной бронзы",
    "Concentrated Bronze Hoe": "Мотыга из концентрированной бронзы",
    "Feral Paws": "Дикие лапы",
    "Power Gauntlet": "Перчатка силы",
    "Stone Glove": "Каменная перчатка",
    "Dolphin Flippers": "Дельфиньи ласты",
    "Scrappy Obsidian Skull": "Обшарпанный обсидиановый череп",
    "Ancient Obsidian Skull": "Древний обсидиановый череп",
    "Animal Leather Helmet": "Кожаный шлем из шкуры животного",
    "Animal Leather Chestplate": "Кожаный нагрудник из шкуры животного",
    "Animal Leather Leggings": "Кожаные поножи из шкуры животного",
    "Animal Leather Boots": "Кожаные сапоги из шкуры животного",
    "Animal Leather Horse Armor": "Кожаный конский доспех из шкуры животного",
    "Animal Leather": "Кожа животного",
    "Quality Leather Belt": "Ремень из качественной кожи",
    "Diamond Pickarang": "Алмазный пикаранг",
    "Netherite Pickarang": "Незеритовый пикаранг",
    "Bottled Cloud": "Облако в бутылке",
    "Stinky Hat": "Вонючий колпак",
    "Debug Item": "Отладочный предмет",
    "Will Power Anointment": "Помазание волей",
    "Dungeon Tester": "Тестер подземелий",
    "Laser Gatling": "Лазерный миниган",
    "Blighted Oak Sapling": "Саженец поражённого дуба",
    "Blighted Oak Log": "Бревно поражённого дуба",
    "Blighted Oak Wood": "Древесина поражённого дуба",
    "Stripped Blighted Oak Log": "Очищенное бревно поражённого дуба",
    "Stripped Blighted Oak Wood": "Очищенная древесина поражённого дуба",
    "Blighted Oak Planks": "Доски поражённого дуба",
    "Blighted Oak Stairs": "Ступени поражённого дуба",
    "Blighted Oak Slab": "Плита поражённого дуба",
    "Blighted Oak Fence": "Забор поражённого дуба",
    "Blighted Oak Fence Gate": "Калитка поражённого дуба",
    "Blighted Oak Door": "Дверь поражённого дуба",
    "Blighted Oak Trapdoor": "Люк поражённого дуба",
    "Blighted Oak Button": "Кнопка поражённого дуба",
    "Blighted Oak Pressure Plate": "Нажимная пластина поражённого дуба",
    "Blighted Stone Pressure Plate": "Нажимная пластина поражённого камня",
    "Blighted Stone Button": "Кнопка поражённого камня",
    "Eye Of Frostbitten": "Око обмороженного",
    "Iron Scrap": "Железный лом",
    "Mist Charge": "Туманный заряд",
    "Foggy Essence": "Туманная эссенция",
    "Erosion Rock Bricks": "Эрозионные каменные кирпичи",
    "PolaRice": "ПолаРайс",
    "Skin Tissue": "Кожная ткань",
    "Cracking Bone": "Треснувшая кость",
    "Baal": "Баал",
    "§6Insignia of Lightforged Benediction": "§6Эмблема Благословения Светокованного",
}


def main():
    tr = json.loads((WORK / "kubejs_ru.json").read_text(encoding="utf-8"))
    total_files = total_keys = 0
    missing: list[tuple[str, str]] = []

    for en_file in sorted((ROOT / "kubejs/assets").glob("*/lang/en_us.json")):
        ns = en_file.parent.parent.name
        data = json.loads(en_file.read_text(encoding="utf-8"))
        out = {}
        for key, value in data.items():
            if not isinstance(value, str):
                out[key] = value
                continue
            ru = tr.get(value) or LANGJS_NAMES.get(value)
            if ru is None:
                missing.append((ns, key))
                continue
            out[key] = ru
        target = en_file.parent / "ru_ru.json"
        target.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        total_files += 1
        total_keys += len(out)
        print(f"  {ns:22s} {len(out):4d}/{len(data):4d} ключей")

    print(f"файлов: {total_files}, ключей: {total_keys}")
    if missing:
        print(f"БЕЗ ПЕРЕВОДА ({len(missing)}):")
        for ns, key in missing[:20]:
            print(f"   {ns}:{key}")

    # --- блок ru_ru в lang.js ---
    src = LANG_JS.read_text(encoding="utf-8")
    renames = re.findall(r"event\.renameItem\('([^']+)',\s*'((?:[^'\\]|\\.)*)'\)", src)
    adds = re.findall(r"event\.add\('([^']+)',\s*'((?:[^'\\]|\\.)*)'\)", src)
    lines = []
    for item_id, name in renames:
        ru = tr.get(name) or LANGJS_NAMES.get(name)
        if ru:
            lines.append(f" event.renameItem('{item_id}', '{ru}')")
    for key, value in adds:
        ru = tr.get(value) or LANGJS_NAMES.get(value)
        if ru:
            lines.append(f" event.add('{key}', '{ru}')")

    block = ('\n// Русская локализация: те же переименования, что и для en_us\n'
             'ClientEvents.lang("ru_ru", event => {\n'
             + "\n".join(lines) + "\n});\n")
    if 'ClientEvents.lang("ru_ru"' in src:
        src = re.sub(r'\n// Русская локализация.*?\n\}\);\n', block, src, flags=re.S)
    else:
        src = src.rstrip() + "\n" + block
    LANG_JS.write_text(src, encoding="utf-8")
    print(f"в lang.js добавлено строк в ru_ru: {len(lines)} "
          f"(из {len(renames)} renameItem + {len(adds)} add)")


if __name__ == "__main__":
    main()
