# -*- coding: utf-8 -*-
"""Терминологический словарь: выравнивание по head-существительному.

Для фразы вида "Iron Ingot" -> "Железный слиток" head EN = "ingot",
head RU = "слиток". Голосуем за оба края RU-фразы, берём доминирующий.
Так термины собираются чисто, а не по совместной встречаемости.
"""
import json, re, collections, os

WS = "/home/ax/Documents/Opencode/Для сборок переводов/linggango/workspace"
ENW = re.compile(r"[A-Za-z][A-Za-z'\-]*")
RUW = re.compile(r"[а-яё][а-яё\-]*", re.I)

EN_STOP = set("""the a an of and or to in on at for with from is are was were be been
no not it its as by all any can will would could should may might do does did you your
this that these those if then else than so such but not no nor only own same too very
when where which who whom what how why here there all also more most other another
each every some any many much few less least own same new old first last next
deals gives grants grants bonus increase decreases chance chance to chance amount
damage health speed level block blocks item items effect effects bonus extra
""".split())


MANUAL = {
    "ingot": "слиток", "nugget": "самородок", "block": "блок",
    "sword": "меч", "axe": "топор", "pickaxe": "кирка", "shovel": "лопата",
    "helmet": "шлем", "chestplate": "нагрудник", "leggings": "поножи",
    "boots": "сапоги", "ring": "кольцо", "amulet": "амулет", "scroll": "свиток",
    "chest": "сундук", "potion": "зелье", "bucket": "ведро", "banner": "знамя",
    "torch": "факел", "coin": "монета",
    "crystal": "кристалл", "shard": "осколок", "blade": "клинок", "bow": "лук",
    "shield": "щит", "weapon": "оружие", "tool": "инструмент",
    "stairs": "лестница", "slab": "плита",
    "mythic": "мифический", "legendary": "легендарный", "epic": "эпический",
    "cursed": "проклятый", "undead": "нежить", "essence": "эссенция",
    "armor": "броня",
}


def build_terms(min_count=4, min_ratio=0.5):
    g = json.loads(open(f"{WS}/work/mods_ru.json", encoding="utf-8").read())
    votes = collections.defaultdict(collections.Counter)
    for en, ru in g.items():
        if not isinstance(ru, str):
            continue
        ew = ENW.findall(en)
        rw = RUW.findall(ru)
        if len(ew) < 2 or len(rw) < 2:
            continue
        head = ew[-1].lower()
        if head in EN_STOP or len(head) < 3:
            continue
        for r in (rw[-1].lower(), rw[0].lower()):
            votes[head][r] += 1
    # сначала лучший кандидат по каждому head
    best = {}
    for w, c in votes.items():
        tot = sum(c.values())
        if tot < min_count:
            continue
        r, cr = c.most_common(1)[0]
        if cr / tot >= min_ratio:
            best[w] = r
    # убираем неоднозначные: один русский термин не должен тянуться к двум head'ам
    rev = collections.defaultdict(set)
    for w, r in best.items():
        rev[r].add(w)
    ambiguous = {r for r, ws in rev.items() if len(ws) > 1}
    terms = {w: r for w, r in best.items() if r not in ambiguous}
    return terms


if __name__ == "__main__":
    t = build_terms()
    print("терминов:", len(t))
    json.dump(t, open("/tmp/terms2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    probe = ["ingot", "block", "nugget", "dust", "sword", "axe", "helmet", "chestplate",
             "leggings", "boots", "ring", "amulet", "staff", "wand", "scroll", "tome",
             "chest", "ore", "gem", "crystal", "plate", "slab", "stairs", "shield",
             "bucket", "potion", "coin", "torch", "essence", "core", "fragment", "shard",
             "bow", "arrow", "bottle", "jar", "meat", "creature", "blade", "material",
             "hammer", "pickaxe", "shovel", "hoe", "furnace", "anvil", "enchantment",
             "potion", "essence", "essence", "rune", "runes", "relic", "talisman",
             "book", "banner", "key", "lantern", "map", "compass", "bell", "horn",
             "wand", "robe", "mask", "amulet", "necklace", "bracelet", "pendant",
             "blade", "katana", "spear", "glaive", "halberd", "cannon", "turret"]
    for s in probe:
        print(f"  {s:<12} -> {t.get(s,'?')}")
