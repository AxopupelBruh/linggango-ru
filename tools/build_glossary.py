"""Строит глоссарий EN→RU из уже существующих переводов: ванилла + моды.

Логика: если мод уже переведён на русский, его ru_ru.json — авторитетный источник
названий. Ключ ru_ru.json совпадает с ключом en_us.json того же мода, значит мы знаем
точную пару «английское название → официальное русское название». Эти пары и есть
глоссарий: с их помощью перевод остальных модов и квестов будет называть предметы
теми же словами, что и игра.
"""
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS = ROOT / "mods"
VANILLA_JAR = Path("/home/ax/Documents/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar")
VANILLA_ASSETS = Path("/home/ax/Documents/curseforge/minecraft/Install/assets")
OUT = Path(__file__).parent / "glossary.json"


def vanilla_lang() -> tuple[dict, dict]:
    """Достаёт ванильные en_us/ru_ru.

    en_us.json лежит внутри клиентского jar, а ru_ru.json приходит отдельным
    объектом ассетов (в индексе 5.json для 1.20.1).
    """
    en: dict = {}
    ru: dict = {}
    if VANILLA_JAR.exists():
        with zipfile.ZipFile(VANILLA_JAR) as z:
            try:
                en = json.loads(z.read("assets/minecraft/lang/en_us.json").decode("utf-8"))
            except KeyError:
                pass
    index_path = VANILLA_ASSETS / "indexes/5.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))["objects"]
        meta = index.get("minecraft/lang/ru_ru.json")
        if meta:
            h = meta["hash"]
            path = VANILLA_ASSETS / "objects" / h[:2] / h
            if path.exists():
                ru = json.loads(path.read_text(encoding="utf-8"))
    return en, ru

# Слова, которые нельзя «терминологизировать»: иначе текст рассыплется
STOP = {
    # служебные
    "The", "A", "An", "And", "Or", "But", "In", "On", "At", "To", "Of", "For", "With",
    "From", "By", "As", "Is", "Are", "Was", "Were", "Be", "Been", "Being", "If", "Then",
    "Than", "So", "Such", "No", "Not", "Nor", "Too", "Very", "Can", "Will", "Would",
    "Should", "Could", "May", "Might", "Must", "Do", "Does", "Did", "Have", "Has", "Had",
    "Here", "There", "When", "Where", "What", "Why", "How", "Who", "Which", "That",
    "This", "These", "Those", "It", "Its", "He", "She", "His", "Her", "They", "Their",
    "We", "Our", "You", "Your", "Yourself", "I", "My", "Me", "Itself", "Them", "Us",
    # глаголы и наречия
    "Get", "Got", "Make", "Made", "Making", "Use", "Used", "Using", "Find", "Found",
    "Kill", "Killed", "Defeat", "Defeated", "Craft", "Crafted", "Build", "Built",
    "Upgrade", "Upgraded", "Equip", "Equipped", "Wear", "Worn", "Place", "Placed",
    "Give", "Start", "Started", "Begin", "Begun", "Read", "Hold", "Complete", "Completed",
    "Reach", "Obtain", "Obtained", "Bring", "Need", "Needs", "Requires", "Required",
    "Add", "Added", "Remove", "Removed", "Open", "Opened", "Close", "Closed",
    "Drop", "Dropped", "Pick", "Pickup", "Attack", "Attacked", "Damage", "Damaged",
    "Break", "Broke", "Dig", "Mine", "Mined", "Smelt", "Smelted", "Brew", "Brewed",
    "Summon", "Summoned", "Tame", "Tamed", "Win", "Won", "Lose", "Lost", "See", "Saw",
    "Know", "Known", "Take", "Took", "Wear", "Wield", "Charge", "Charged", "Unlock",
    "Increase", "Decrease", "Select", "Selected", "Choose", "Chosen", "Press", "Shift",
    "Ctrl", "Alt", "Left", "Right", "Middle", "Enter", "Space", "Back", "Next", "Prev",
    "Previous", "Menu", "Screen", "Button", "Slot", "Slots", "Set", "Type", "Name",
    "All", "Any", "Some", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
    "Eight", "Nine", "Ten", "New", "Old", "More", "Less", "Most", "Other", "Others",
    "Now", "Then", "Still", "Also", "Just", "Only", "Even", "Ever", "Never", "Always",
    "Every", "Each", "Both", "Few", "Own", "Same", "Such", "Free", "Full", "Empty",
    "None", "Unknown", "Default", "Custom", "Normal", "Special", "Basic", "Advanced",
    "Simple", "Easy", "Hard", "Best", "Good", "Bad", "Great", "Small", "Big", "Large",
    "Level", "Tier", "Tiers", "Levels", "Point", "Points", "Total", "Number", "Numbers",
    "Click", "Read", "Note", "Tip", "Tips", "Info", "Warning", "Error", "Config",
    "Option", "Options", "Setting", "Settings", "Enable", "Disable", "Enabled",
    "Disabled", "Item", "Items", "Block", "Blocks", "Entity", "World", "Biome",
    "Biomes", "Dimension", "Armor", "Armour", "Shield", "Weapon", "Weapons", "Sword",
    "Swords", "Axe", "Axes", "Pickaxe", "Pickaxes", "Shovel", "Hoe", "Bow", "Bows",
    "Staff", "Wand", "Ring", "Rings", "Necklace", "Amulet", "Charm", "Charms",
    "Relic", "Relics", "Trinket", "Talisman", "Boots", "Helmet", "Chestplate",
    "Leggings", "Offhand", "Mainhand", "Tooltip", "Hint", "Advancement", "Recipe",
    "Recipes", "Crafting", "Smelting", "Furnace", "Blast", "Forge", "Anvil",
    "Smithing", "Player", "Players", "Inventory", "Chest", "Ore", "Ores", "Ingot",
    "Ingots", "Nugget", "Nuggets", "Dust", "Dusts", "Gem", "Gems", "Crystal",
    "Crystals", "Book", "Books", "Page", "Pages", "Chapter", "Chapters", "Quest",
    "Quests", "Guide", "Guides", "Wiki", "Spell", "Spells", "School", "Schools",
    "Element", "Elements", "Rune", "Runes", "Sigil", "Sigils", "Mana", "Energy",
    "Health", "Hunger", "Thirst", "Xp", "Tame", "Personal", "Elite", "Ultimate",
    "Master", "Expert", "Apprentice", "Novice", "Rare", "Common", "Uncommon", "Legendary",
    "Mythic", "Epic", "Unusual", "Strange", "Void", "Fire", "Ice", "Water", "Air",
    "Earth", "Light", "Dark", "Holy", "Nature", "Soul", "Blood", "Storm", "Wind",
    "Shadow", "Frost", "Lightning", "Thunder", "Arcane", "Eldritch", "Unholy",
    "Winter", "Summer", "Spring", "Autumn", "Fall", "Night", "Day", "Sun", "Moon",
    "Star", "Stars", "Sky", "Sea", "Ocean", "River", "Mountain", "Forest", "Desert",
    "Jungle", "Swamp", "Plains", "Hills", "Cave", "Caves", "Hell", "Nether", "End",
    "Overworld", "Abyss", "Void", "Sky", "Aether", "Twilight",
}


# Строки, которые не трогаем: служебные, форматированные, ID
SKIP_VALUE = re.compile(r"[§%{}<>]|\\[a-z]|\bitem\.|minecraft:|\.json|\.snbt|http", re.I)
LATIN_ONLY = re.compile(r"^[A-Za-z0-9\s'’\-.,:;!?()\[\]&/+#*%\"<>=]+$")
HAS_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def name_like(value: str) -> bool:
    """Похоже на имя/название (а не на обычную фразу)."""
    v = value.strip()
    if not v or len(v) > 70:
        return False
    if "\n" in v or ":" in v:
        return False
    if SKIP_VALUE.search(v):
        return False
    words = v.split()
    if not (1 <= len(words) <= 6):
        return False
    # начинается с заглавной буквы — названия предметов в игре так и выглядят
    if not v[0].isupper():
        return False
    if v in STOP:
        return False
    return True


def ru_usable(en: str, ru: str) -> bool:
    ru = ru.strip()
    if not ru or ru == en.strip():
        return False
    if SKIP_VALUE.search(ru):
        return False
    # перевод должен содержать кириллицу (иначе это не перевод)
    if not HAS_CYRILLIC.search(ru):
        return False
    # одиночное слово: русская форма должна быть заглавной (именной),
    # иначе это родительный падеж («незерита») — такое в глоссарий не годится
    if " " not in en.strip() and not ru[0].isupper():
        return False
    return True


def collect_pairs():
    pairs = defaultdict(Counter)  # en -> Counter(ru)
    strong = defaultdict(Counter)  # en -> Counter(ru) для имён собственных

    def add(en_map, ru_map, source):
        for key, en_val in en_map.items():
            ru_val = ru_map.get(key)
            if not isinstance(en_val, str) or not isinstance(ru_val, str):
                continue
            if not name_like(en_val) or not ru_usable(en_val, ru_val):
                continue
            en = en_val.strip()
            pairs[en][ru_val.strip()] += 1
            # «сильный» термин: имя из item/block/entity-ключа или Title Case
            ru = ru_val.strip()
            # отсекаем описательные переводы («Altar» -> «Алтарь для книги теней»):
            # настоящее название сопоставимо по длине
            sane = len(ru) <= 2.0 * len(en) + 8
            if not sane:
                continue
            if key.split(".")[0] in ("item", "block", "entity", "fluid", "effect",
                                     "attribute", "enchantment", "potion", "villager"):
                strong[en][ru] += 1
            elif is_title_case(en) and len(en.split()) > 1:
                strong[en][ru] += 1

    # 1. Ванилла
    ven, vru = vanilla_lang()
    if ven:
        add(ven, vru, "minecraft")
        print(f"ванилла: {len(ven)} en / {len(vru)} ru")
    else:
        print("ВНИМАНИЕ: ванильные lang не найдены")

    # 2. Моды
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        en_map, ru_map = {}, {}
        for name in z.namelist():
            if "/lang/" not in name:
                continue
            folder, fname = name.rsplit("/", 1)
            if fname not in ("en_us.json", "ru_ru.json"):
                continue
            try:
                data = json.loads(z.read(name).decode("utf-8"))
            except Exception:
                continue
            (en_map if fname == "en_us.json" else ru_map)[folder] = data
        for folder, en in en_map.items():
            add(en, ru_map.get(folder, {}), jar.stem)
    return pairs, strong


def is_title_case(value: str) -> bool:
    """Каждое значимое слово с заглавной — признак имени собственного."""
    small = {"of", "the", "and", "for", "with", "in", "on", "at", "to", "from", "or"}
    words = [w for w in value.split() if w.lower() not in small]
    return bool(words) and all(w[0].isupper() for w in words)


def main():
    pairs, strong = collect_pairs()
    glossary = {}
    conflicts = []
    for en, ru_counter in pairs.items():
        # если один вариант — расширение другого («Алтарь» / «Алтарь для книги теней»),
        # берём более общий (короче)
        cands = list(ru_counter.items())
        shorter = [c for c in cands if len(c[0]) < len(max(cands, key=lambda x: len(x[0]))[0])]
        if shorter:
            cands = shorter or cands
        best = max(cands, key=lambda kv: (kv[1], kv[0][:1].isupper(), -len(kv[0])))
        ru = best[0]
        if len(ru_counter) > 1:
            conflicts.append((en, ru_counter.most_common()))
        s = strong.get(en)
        glossary[en] = {
            "ru": ru,
            "strong": bool(s and s.most_common(1)[0][0] == ru),
        }
    OUT.write_text(json.dumps(glossary, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    n_strong = sum(1 for v in glossary.values() if v["strong"])
    print(f"в глоссарии {len(glossary)} терминов (сильных: {n_strong})")
    print(f"конфликтов (несколько вариантов): {len(conflicts)}")
    for en, c in conflicts[:12]:
        print("  ", en, "->", c)
    print("\nпримеры:")
    for k in ["Deepslate", "Warden", "Obsidian", "Redstone", "Sculk", "Enderman",
              "Pillager", "Ravager", "Blaze", "Ghast", "Copper", "Amethyst",
              "Nether Wart", "Elytra", "Totem of Undying", "Iron Sword",
              "Abyssal Chasm", "Iron Colossus", "Pearl", "Netherite"]:
        v = glossary.get(k)
        if not v:
            print(f"   {k:22s} -> (нет)")
        else:
            mark = "  [сильный]" if v["strong"] else ""
            print(f"   {k:22s} -> {v['ru']}{mark}")


if __name__ == "__main__":
    main()
