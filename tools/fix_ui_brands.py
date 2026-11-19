"""Переперевод строк, где название мода (бренд) может быть транслитерировано.

Зачем: DeepL переводит неизвестные имена собственные («Ars Nouveau» → «Ар Нуво»).
По правилам пака бренды остаются на английском. Поэтому бренды маскируются
плейсхолдерами ДО перевода и подставляются обратно как есть.

Бренды берём из mods.toml всех модов инстанса (displayName) + modId,
отфильтровывая обычные английские слова.

Результат: обновляет work/ui_strings_ru.json и work/cache_deepl.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from deepl_backend import DeepLBackend  # noqa: E402
from fix_java_strings import (  # noqa: E402
    load_terms, postprocess, translate_all, validate,
)

# обычные слова — их не считаем брендами (одноименные моды: Create, Jade…)
STOPWORDS = {
    "create", "makes", "make", "build", "more", "add", "additions", "things",
    "the", "and", "for", "with", "you", "your", "new", "all", "better", "big",
    "core", "mod", "mods", "lib", "api", "common", "network", "client",
    "server", "util", "utils", "forge", "fabric", "neoforge", "loader",
    "support", "helper", "tools", "tool", "world", "block", "blocks",
    "item", "items", "back", "port", "edition", "classic", "ultimate",
    "deluxe", "premium", "pro", "plus", "ultra", "mega", "mini", "nano",
    "second", "third", "first", "one", "two", "three", "four", "five",
    "sun", "moon", "star", "stars", "void", "soul", "blood", "iron", "gold",
    "nether", "end", "overworld", "red", "blue", "green", "yellow", "white",
    "black", "light", "dark", "deep", "shadow", "shade", "spirit", "souls",
    "power", "powers", "energy", "matter", "life", "time", "space", "worlds",
    "network", "machine", "factory", "generator", "storage", "chest", "ore",
    "ores", "gem", "gems", "crystal", "crystals", "rune", "runes", "spell",
    "spells", "potion", "potions", "mob", "mobs", "monster", "monsters",
    "creature", "creatures", "dragon", "dragons", "knight", "knights",
    "wizard", "wizards", "dungeon", "dungeons", "dimension", "dimensions",
    "biome", "biomes", "structure", "structures", "gen", "gens", "craft",
    "crafting", "machine", "upgrade", "upgrades", "gear", "weapon",
    "weapons", "armor", "armour", "helmet", "chestplate", "leggings", "boots",
    "sword", "axe", "pickaxe", "shovel", "hoe", "tool", "tools", "farm",
    "farming", "cooking", "food", "season", "seasons", "winter", "spring",
    "summer", "autumn", "fall", "winter", "tavern", "inn", "keep", "castle",
    "kingdom", "empire", "realm", "world", "town", "city", "village",
    "graveyard", "crypt", "tomb", "grave", "ruins", "tower", "gate", "walls",
    "bridge", "road", "path", "farmland", "garden", "park", "forest",
    "swamp", "jungle", "desert", "savanna", "plains", "hills", "mountains",
    "ocean", "river", "island", "islands", "valley", "shore", "coast",
    "cliff", "cave", "caves", "abyss", "ritual", "rituals", "curse",
    "curses", "blight", "blight", "rot", "decay", "ruin", "doom", "hive",
    "swarm", "pack", "clan", "faction", "order", "cult", "church", "temple",
    "shrine", "altar", "obelisk", "monument", "statue", "idol", "relic",
    "relics", "artifact", "artifacts", "treasure", "loot", "chests",
    "pvp", "rpg", "fps", "ui", "gui", "hp", "mp", "xp", "npc", "npcs",
    "ai", "ml", "ui", "lib", "loader", "core", "common", "fabric", "forge",
}

# принудительно: сокращения и названия, которые нельзя терять
FORCE = ["JEI", "REI", "FTB", "WTHIT", "AE2", "EMI", "JEI", "KubeJS",
         "Forge", "Minecraft", "Curios", "JEI", "Patchouli", "Architectury",
         "Immersive Portals", "Mekanism Tools", "Mekanism", "Ars Nouveau",
         "Farmer's Delight", "Applied Energistics 2", "Blood Magic",
         "The Undergarden", "Just Direction Things", "Legendary Monsters",
         "Odd Accessories", "Sophisticated Storage", "Create Crafts & Additions",
         "Alex's Mobs", "Alex's Caves", "Botania", "Ad Astra", "Adventurer's Time"]


def build_brands() -> list[str]:
    data = json.loads((WORK / "mod_brands.json").read_text(encoding="utf-8"))
    brands: set[str] = set()

    for name in data["names"]:
        name = name.strip().strip('"').strip()
        if not name or len(name) < 3:
            continue
        if " " in name:
            brands.add(name)
        else:
            low = name.lower()
            if low not in STOPWORDS and len(name) >= 5:
                brands.add(name)

    for mid in data["ids"]:
        mid = mid.strip()
        if len(mid) >= 5 and mid.lower() not in STOPWORDS:
            brands.add(mid)

    for f in FORCE:
        brands.add(f)

    # убираем бренды, полностью содержащиеся в других (короче оставляем)
    out = sorted(brands, key=len, reverse=True)
    result: list[str] = []
    for b in out:
        if not any(b != r and b.lower() in r.lower() for r in result):
            result.append(b)
    return sorted(result)


def mask_brands(text: str, brands: list[str]) -> tuple[str, list[str]]:
    """Заменяет бренды на {1000+i}, возвращает список исходных написаний."""
    found: list[str] = []
    out = text
    for b in brands:
        pattern = re.compile(r"(?<![\w])" + re.escape(b) + r"(?![\w])", re.IGNORECASE)
        if not pattern.search(out):
            continue
        def repl(m: re.Match, _b=b) -> str:
            found.append(m.group(0))
            return "{%d}" % (1000 + len(found) - 1)
        out = pattern.sub(repl, out)
    return out, found


def unmask_brands(text: str, found: list[str]) -> str:
    def repl(m: re.Match) -> str:
        i = int(m.group(1)) - 1000
        if 0 <= i < len(found):
            return found[i]
        return m.group(0)
    return re.sub(r"\{(\d{4,})}", repl, text)


def main() -> int:
    src = json.loads((WORK / "ui_strings.json").read_text(encoding="utf-8"))
    out = json.loads((WORK / "ui_strings_ru.json").read_text(encoding="utf-8"))
    brands = build_brands()
    print(f"брендов в списке: {len(brands)}")

    terms = load_terms()
    cache: dict[str, str] = {}
    cache_path = WORK / "cache_deepl.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    affected: list[str] = []
    for s in src:
        masked, found = mask_brands(s, brands)
        if found:
            affected.append(s)
    print(f"строк с брендами: {len(affected)}")

    # маскируем и переводим
    masked_map: dict[str, tuple[str, list[str]]] = {}
    for s in affected:
        masked_map[s] = mask_brands(s, brands)

    backend = DeepLBackend()
    todo = [s for s in affected if masked_map[s][0] not in cache]
    print(f"в кэше: {len(affected) - len(todo)}, переводим: {len(todo)}")
    for i in range(0, len(todo), backend.max_items):
        batch = todo[i:i + backend.max_items]
        masked_texts = [masked_map[s][0] for s in batch]
        try:
            got = backend.translate(masked_texts)
        except Exception as e:
            print(f"  ошибка на батче {i}: {e}")
            break
        for mt, ru in zip(masked_texts, got):
            cache[mt] = ru
        if (i // backend.max_items) % 10 == 0:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    changed = 0
    for s in affected:
        masked, found = masked_map[s]
        ru = cache.get(masked)
        if not ru:
            continue
        ru = unmask_brands(ru, found)
        ru = postprocess(s, ru)
        err = validate(s, ru)
        if err:
            continue
        if ru != out.get(s):
            changed += 1
        out[s] = ru

    (WORK / "ui_strings_ru.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"обновлено переводов: {changed}, всего в словаре: {len(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
