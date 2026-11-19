"""Финальная доводка переводов квестов после аудита 19.11.

Что чиним:
  1. склейки кириллицы и латиницы (4 строки) — «снiffer'ом», «Thermalникогдане»,
     «заменитe» (латинская e), «aи стал»;
  2. разметка вне своего места (2 строки mekanism) и текст после </shadow> (bridges);
  3. явные ошибки перевода (simply_swords, act_0 «нужна топор»);
  4. Terraria: возвращаем формулировку пользователя «по мотивам Terraria»;
  5. массовая нормализация пробелов: пробел перед знаком препинания и двойные
     пробелы, которые остались на стыке текстовых узлов после перевода.

Нормализация не меняет теги — только текстовые узлы.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
RE_TAG = re.compile(r"</?[^>]+>")
RE_SPLIT = re.compile(r"(</?[^>]+>)")


def patch(ru: dict[str, str], en_index: dict, fixes: dict[str, str]) -> tuple[int, list[str]]:
    changed, missing = 0, []
    for old, new in fixes.items():
        hit = None
        if old in ru:
            hit = old
        else:
            norm = old.replace("\u200c", "")
            for k in ru:
                if k.replace("\u200c", "") == norm:
                    hit = k
                    break
        if hit is None:
            missing.append(old)
            continue
        if ru[hit] != new:
            ru[hit] = new
            changed += 1
    return changed, missing


def normalize(text: str) -> str:
    """Убирает пробелы перед знаками препинания и двойные пробелы на стыках тегов."""
    parts = RE_SPLIT.split(text)
    # parts: [текст, тег, текст, тег, ...]
    texts = [i for i, p in enumerate(parts) if i % 2 == 0]
    # 1. схлопываем повторные пробелы внутри текстовых узлов
    for i in texts:
        chunk = parts[i]
        # не трогаем ZWNJ и переводы строк
        chunk = re.sub(r"(?<=\S)[ \t]{2,}", " ", chunk)
        chunk = re.sub(r"[ \t]{2,}(?=\S)", " ", chunk)
        parts[i] = chunk
    # 2. убираем пробел перед пунктуацией на стыке текстовых узлов
    for pos, i in enumerate(texts):
        chunk = parts[i]
        nxt = parts[texts[pos + 1]] if pos + 1 < len(texts) else ""
        if chunk and nxt[:1] and nxt[:1] in ",.!?;:":
            parts[i] = re.sub(r"[ \t]+$", "", chunk)
    # 3. подчищаем края строки
    if texts:
        parts[texts[0]] = parts[texts[0]].lstrip(" \t")
        parts[texts[-1]] = parts[texts[-1]].rstrip(" \t")
    return "".join(parts)


FIXES = {
    # ── склейки ────────────────────────────────────────────────────────────
    "<typewriter><grad from=#C8AE86 to=#C8AE86>Point it\u200c near\u200c the sniffer, not at\u200c it</grad>":
        "<typewriter><grad from=#C8AE86 to=#C8AE86>Направьте его рядом\u200c с\u200c нюхачом, а не прямо на\u200c него</grad>",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Thermal's creosote\u200c was\u200c never\u200c in that\u200c tag. So\u200c you could be\u200c sitting on </grad>"
    "<grad from=#5AB9FF to=#5096FF f=0.8>tanks of the\u200c stuff</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> and\u200c still be told\u200c to go\u200c build a\u200c Coke\u200c Oven\u200c before you\u200c could\u200c make a plank.</grad></shadow>":
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Креозот от\u200c Thermal\u200c никогда\u200c не\u200c входил\u200c в\u200c этот\u200c тег.\u200c Так\u200c что\u200c вы\u200c могли\u200c сидеть\u200c на </grad>"
        "<grad from=#5AB9FF to=#5096FF f=0.8>резервуарах с этим\u200c веществом</grad>"
        "<grad from=#FFFFFF to=#C7C7C7> и\u200c вам\u200c всё равно\u200c скажут\u200c построить\u200c коксовую\u200c печь,\u200c прежде чем\u200c вы\u200c сможете\u200c изготовить\u200c доску.</grad></shadow>",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>While\u200c you\u200c bear the ring, dying\u200c costs\u200c you\u200c a Soul\u200c Crystal. Each\u200c one you lose\u200c takes </grad>"
    "<grad from=#FFC46B to=#FF9E1F f=0.8>10 percent</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> off your maximum\u200c health, permanently, until\u200c you replace it.</grad></shadow>":
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Пока\u200c вы\u200c носите кольцо,\u200c смерть\u200c обходится\u200c вам\u200c в\u200c один\u200c кристалл\u200c души.\u200c Каждый\u200c потерянный\u200c вами\u200c кристалл\u200c снижает\u200c </grad>"
        "<grad from=#FFC46B to=#FF9E1F f=0.8>10 процентов</grad>"
        "<grad from=#FFFFFF to=#C7C7C7> от\u200c вашего\u200c максимального\u200c запаса\u200c здоровья\u200c навсегда,\u200c пока\u200c вы\u200c его\u200c не\u200c замените.</grad></shadow>",

    "aand became\u200c an undead. Now\u200c he controls\u200c them.":
        "И\u200c стал\u200c нежитью.\u200c Теперь\u200c он\u200c контролирует\u200c их.",

    # ── разметка не на месте ──────────────────────────────────────────────
    "<typewriter><grad from=#7FE0B0 to=#7FE0B0>Airy stuff\u200c goes\u200c here</grad>":
        "<typewriter><grad from=#7FE0B0 to=#7FE0B0>Здесь\u200c место\u200c воздушным\u200c штукам</grad>",

    "<typewriter><grad from=#F2C14E to=#F2C14E>A\u200c very\u200c expensive\u200c kettle</grad>":
        "<typewriter><grad from=#F2C14E to=#F2C14E>Очень\u200c дорогой\u200c чайник</grad>",

    "- <shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Water splits\u200c sage\u200c and\u200c yellow dock\u200c evenly</grad></shadow>":
        "- <shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Вода\u200c равномерно\u200c разделяет\u200c шалфей\u200c и\u200c жёлтый\u200c щавель</grad></shadow>",

    # ── ошибки перевода ───────────────────────────────────────────────────
    "<shadow a=0.4><grad from=#E6DCFF to=#8B67DE f=0.6>Blade of the Grotesque</grad></shadow>":
        "<shadow a=0.4><grad from=#E6DCFF to=#8B67DE f=0.6>Клинок гротеска</grad></shadow>",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>You can't just punch a tree! Your hands will hurt.. Logs need an </grad>"
    "<grad from=#F2DDB0 to=#C9A36A f=0.8>axe</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, and an axe needs a few things first.</grad></shadow>":
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Нельзя просто так ударить по дереву кулаком! Руки будут болеть... Для рубки брёвен нужен </grad>"
        "<grad from=#F2DDB0 to=#C9A36A f=0.8>топор</grad>"
        "<grad from=#FFFFFF to=#C7C7C7>, а для топора сначала нужно кое-что ещё.</grad></shadow>",

    # ── Terraria: формулировка пользователя ───────────────────────────────
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>This\u200c is a </grad></shadow>"
    "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Terraria-inspired</shadow></grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>, </grad></shadow>"
    "<shadow a=0.3><grad from=#FFC438 to=#FFE4A3 f=0.8>content-packed</grad></shadow>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> modpack\u200c built to give </grad></shadow>"
    "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Minecraft</shadow></grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> a\u200c whole new\u200c style of progression and adventure.</grad></shadow>":
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Это\u200c </grad></shadow>"
        "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>модпак по мотивам Terraria</shadow></grad>"
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>, </grad></shadow>"
        "<shadow a=0.3><grad from=#FFC438 to=#FFE4A3 f=0.8>насыщенный контентом</grad></shadow>"
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> и\u200c созданный,\u200c чтобы подарить </grad></shadow>"
        "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Minecraft</shadow></grad>"
        "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> совершенно\u200c новый\u200c стиль прохождения и приключений.</grad></shadow>",
}


def tags_of(text: str) -> list[str]:
    return RE_TAG.findall(text)


def main() -> int:
    p = WORK / "quests_ru.json"
    ru = json.loads(p.read_text(encoding="utf-8"))
    en_index = json.loads((WORK / "quests.json").read_text(encoding="utf-8"))

    # проверяем разметку правок до применения
    bad = [k for k, v in FIXES.items() if tags_of(k) != tags_of(v)]
    if bad:
        print(f"РАЗМЕТКА НЕ СОВПАЛА в правках: {len(bad)}")
        for b in bad:
            print("  ", b[:120])
        return 1

    changed, missing = patch(ru, en_index, FIXES)
    if missing:
        print(f"НЕ НАЙДЕНО: {len(missing)}")
        for m in missing[:10]:
            print("  ", m[:120])
    print(f"точечных правок: {changed}")

    # нормализация пробелов
    norm_changed = 0
    for en, text in ru.items():
        new = normalize(text)
        if new != text:
            if tags_of(new) != tags_of(text):
                print("!! нормализация сломала теги:", en_index.get(en))
                return 1
            ru[en] = new
            norm_changed += 1
    print(f"строк с нормализованными пробелами: {norm_changed}")

    p.write_text(json.dumps(ru, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("quests_ru.json записан")
    return 0


if __name__ == "__main__":
    sys.exit(main())
