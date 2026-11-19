"""Детектор пропавших слов: имя из EN потерялось в RU целиком.

Идея: именная часть EN (Capitals + латиница) — это «якоря», которые переводчик
обязан либо оставить латиницей, либо перевести по глоссарию. Если якорь не найден
ни в RU как есть, ни в глоссарии — слово, скорее всего, выброшено.

Не ловит обычные слова, переведённые на русский (для них якоря нет).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

RE_TAG = re.compile(r"</?[^>]+>")
RE_PROPER = re.compile(r"\b([A-Z][A-Za-z]{2,}(?:[ -][A-Z][A-Za-z]{2,})*)\b")
RE_LATIN = re.compile(r"[A-Za-z]")
# служебные слова, начинающиеся с заглавной
STOP = {
    "The", "This", "That", "These", "Those", "When", "Where", "While", "With",
    "Without", "You", "Your", "Yours", "Use", "Using", "Used", "Get", "Give",
    "Craft", "Crafting", "Place", "Placing", "Put", "Hold", "Holding", "Open",
    "Opens", "Make", "Makes", "Making", "Every", "Each", "One", "Two", "Three",
    "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "All", "Any",
    "Some", "There", "Then", "They", "Their", "Them", "Its", "It", "In", "On",
    "At", "Of", "For", "From", "And", "But", "Not", "New", "Now", "Only",
    "Also", "Just", "If", "So", "No", "Yes", "Or", "As", "By", "Do", "Does",
    "Did", "Can", "Cannot", "Will", "Would", "Should", "Must", "May", "More",
    "Most", "Less", "Before", "After", "First", "Last", "Next", "One",
    "Nothing", "Something", "Anything", "Everything", "Never", "Always",
    "However", "Instead", "Otherwise", "Meanwhile", "Still", "Already",
    "Another", "Both", "Either", "Neither", "Few", "Many", "Much", "Same",
    "Well", "Even", "Back", "Down", "Over", "Under", "Through", "Between",
    "Around", "Because", "While", "Whether", "Because", "Chapter", "Level",
    "Tier", "Step", "Tip", "Note", "Warning", "Info", "Success", "Danger",
    "Quest", "Quests", "Recipe", "Recipes", "Item", "Items", "Block", "Blocks",
    "Mob", "Mobs", "Boss", "Bosses", "Armor", "Weapon", "Weapons", "Tool",
    "Tools", "Shield", "Shields", "Elytra", "Potion", "Potions", "Effect",
    "Effects", "Enchant", "Enchants", "Biome", "Biomes", "Dimension",
    "Dimensions", "Structure", "Structures", "Ore", "Ores", "Ingot", "Ingots",
    "Gem", "Gems", "Crystal", "Crystals", "Core", "Cores", "Dust", "Dust",
    "Wand", "Wands", "Scroll", "Scrolls", "Rune", "Runes", "Relic", "Relics",
    "Skill", "Skills", "Ability", "Abilities", "Power", "Powers", "Level",
    "Health", "Damage", "Speed", "Attack", "Defense", "Armor", "Resistance",
    "Luck", "Magic", "Mana", "Energy", "Fuel", "Power", "Time", "Day", "Night",
    "Spring", "Summer", "Fall", "Winter", "Overworld", "Nether", "End",
    "Sky", "Earth", "Fire", "Water", "Air", "Ice", "Stone", "Wood", "Metal",
    "Gold", "Iron", "Copper", "Silver", "Diamond", "Netherite", "Emerald",
    "Lapis", "Redstone", "Quartz", "Obsidian", "Sand", "Dirt", "Grass",
    "Wool", "Clay", "Brick", "Glass", "Paper", "Book", "Books", "Page",
    "Pages", "Line", "Lines", "Text", "Texts", "Number", "Numbers", "Percent",
    "Click", "Left", "Right", "Shift", "Control", "Key", "Keys", "Keybind",
    "Mouse", "Button", "Screen", "Menu", "Chat", "Message", "Messages",
    "Server", "Client", "Player", "Players", "Mob", "Entity", "Entities",
}


def strip_tags(text: str) -> str:
    return RE_TAG.sub("\x00", text)


def anchors(en: str) -> list[str]:
    """Именные якоря EN: собственные существительные и названия модов."""
    out: list[str] = []
    for part in strip_tags(en).split("\x00"):
        for m in RE_PROPER.finditer(part):
            w = m.group(1)
            head = w.split()[0]
            if head in STOP or w in STOP:
                continue
            out.append(w)
    return out


def main() -> None:
    ru = json.loads((WORK / "quests_ru.json").read_text(encoding="utf-8"))
    en_index = json.loads((WORK / "quests.json").read_text(encoding="utf-8"))
    glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))

    # термин → русские варианты (из глоссария)
    term_ru: dict[str, list[str]] = {}
    for en, val in glossary.items():
        if isinstance(val, dict):
            r = val.get("ru")
        else:
            r = val
        if r:
            term_ru.setdefault(en.lower(), []).append(r)

    flagged: list[tuple[str, list[str]]] = []
    for en, ru_text in ru.items():
        if not ru_text:
            continue
        low = ru_text.lower()
        missing = []
        for a in anchors(en):
            al = a.lower()
            if al in low:
                continue
            variants = term_ru.get(al, [])
            if any(v.lower() in low for v in variants):
                continue
            # часть многословного имени могла остаться в любом слове
            parts = [p for p in a.split() if len(p) > 2]
            if parts and all(p.lower() in low for p in parts):
                continue
            missing.append(a)
        if missing:
            flagged.append((en, missing))

    print(f"строк с пропавшими якорями: {len(flagged)}")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    for en, miss in flagged[:limit]:
        loc = en_index.get(en, ["?"])[0]
        print(f"  {loc} :: {', '.join(miss)}")
        print(f"      {en[:150]}")
    if len(flagged) > limit:
        print(f"… ещё {len(flagged) - limit}")


if __name__ == "__main__":
    main()
