"""Точечные правки переводов квестов: мусорные маркеры <x_N/> и пропавшие слова.

Причина мусора: при переводе движком плейсхолдер вида <x_21/> попадал в результат
(модель «склеивала» его с обычным текстом). Причина пропажи слов: модель
перестраивала фразу и выбрасывала имя (например «Terraria»).

Здесь переводы заданы вручную — по сегментам разметки. Скрипт проверяет, что
набор и порядок тегов в RU совпадают с EN, и только потом подставляет строку.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
RE_TAG = re.compile(r"</?[^>]+>")

# EN → RU. Переводы собраны вручную, разметка один в один.
FIXES: dict[str, str] = {
    # ── introducing: пропало слово Terraria ────────────────────────────────
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>This\u200c is a </grad></shadow>"
    "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Terraria-inspired</shadow></grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>, </grad></shadow>"
    "<shadow a=0.3><grad from=#FFC438 to=#FFE4A3 f=0.8>content-packed</grad></shadow>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> modpack\u200c built to give </grad></shadow>"
    "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Minecraft</shadow></grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> a\u200c whole new\u200c style of progression and adventure.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Это\u200c </grad></shadow>"
    "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Terraria-вдохновлённый</shadow></grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>, </grad></shadow>"
    "<shadow a=0.3><grad from=#FFC438 to=#FFE4A3 f=0.8>насыщенный контентом</grad></shadow>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> модпак,\u200c созданный,\u200c чтобы подарить </grad></shadow>"
    "<grad from=#4DDB58 to=#C1F5C5 f=0.8><shadow a=0.3>Minecraft</shadow></grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> совершенно\u200c новый\u200c стиль прохождения и приключений.</grad></shadow>",

    # ── belts ───────────────────────────────────────────────────────────────
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>The\u200c halo\u200c drops from the </grad>"
    "<grad from=#2FB8B0 to=#A8F0EA f=0.8>Virtue</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, the </grad>"
    "<grad from=#2FB8B0 to=#A8F0EA f=0.8>4000\u200c health</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> angel you\u200c summon by\u200c throwing\u200c an\u200c Unholy Lance\u200c at\u200c the sky.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Ореол\u200c выпадает из </grad>"
    "<grad from=#2FB8B0 to=#A8F0EA f=0.8>Равиил</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, </grad>"
    "<grad from=#2FB8B0 to=#A8F0EA f=0.8>4000\u200c здоровья</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> ангела,\u200c которого вы\u200c призываете,\u200c бросая Нечестивое копьё в небо.</grad></shadow>",

    # ── bleed_magic ─────────────────────────────────────────────────────────
    "[!warn] It also speeds up\u200c how\u200c fast an empty\u200c Altar loses\u200c crafting progress. That\u200c is\u200c only\u200c a problem\u200c if\u200c you keep starting crafts\u200c you cannot\u200c pay\u200c for.":
    "[!warn] Также ускоряет то,\u200c как быстро пустой Алтарь теряет прогресс создания. Это проблема только тогда, когда вы продолжаете начинать создания, за которые не можете заплатить.",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Collects\u200c Will from ranged\u200c kills, and spends </grad>"
    "<grad from=#FFD98A to=#FFB347 f=0.8>1\u200c Will</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> every time\u200c you\u200c fire.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Собирает Волю за убийства с дальнего боя и тратит </grad>"
    "<grad from=#FFD98A to=#FFB347 f=0.8>1\u200c Воля</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> каждый раз,\u200c когда вы\u200c стреляете.</grad></shadow>",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Most\u200c recipes\u200c want nowhere\u200c near\u200c fifty, so it does not\u200c burn\u200c a crystal every\u200c time. It\u200c takes\u200c one </grad>"
    "<grad from=#FF7B7B to=#FF3B3B f=0.8>only as\u200c often\u200c as the real\u200c cost works out to</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, which\u200c comes\u200c out exact over\u200c a run. You\u200c still need\u200c one\u200c sitting\u200c in the\u200c port\u200c before anything starts.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Большинство рецептов требуют далеко не пятьдесят, поэтому он не сжигает кристалл каждый раз. Он берёт один </grad>"
    "<grad from=#FF7B7B to=#FF3B3B f=0.8>только столько раз, сколько выходит по настоящей стоимости</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>,\u200c что за забег выходит точно. Вам всё равно нужен один в порту, прежде чем что-либо начнётся.</grad></shadow>",

    # ── deeper_and_darker_2 ────────────────────────────────────────────────
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Vanilla gave\u200c the Deep\u200c Dark one mob, one structure and\u200c no reason\u200c to ever go\u200c back. </grad>"
    "<grad from=#35FCF9 to=#12B7C4 f=0.8>Deeper\u200c and Darker</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> finishes\u200c the\u200c job. It adds a full\u200c second\u200c layer to\u200c the\u200c world, a\u200c dimension called the </grad>"
    "<grad from=#35FCF9 to=#12B7C4 f=0.8>Otherside</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, which\u200c sits\u200c below bedrock and\u200c is reached by killing\u200c the\u200c one thing down\u200c there that\u200c can definitely\u200c kill\u200c you\u200c back..</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Ванилла дала Глубокой тьме одного моба, одну структуру и ни одной причины возвращаться. </grad>"
    "<grad from=#35FCF9 to=#12B7C4 f=0.8>Глубже и мрачнее</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> доводит дело до конца. Мод добавляет миру целый второй слой — измерение под названием </grad>"
    "<grad from=#35FCF9 to=#12B7C4 f=0.8>Другая сторона</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>,\u200c которое находится ниже бедрока и доступно только через убийство той самой вещи внизу, способной точно убить вас в ответ..</grad></shadow>",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Amber\u200c blocks\u200c generate all\u200c over the </grad></shadow>"
    "<grad from=#35FCF9 to=#12B7C4 f=0.8>Overcast Columns</grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> and turn up\u200c in temple\u200c chests. Every\u200c naturally placed\u200c one has something\u200c sealed\u200c inside it.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Янтарные блоки генерируются по всему </grad></shadow>"
    "<grad from=#35FCF9 to=#12B7C4 f=0.8>Overcast Columns</grad>"
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7> и попадаются в сундуки храмов. В каждом из них что-то запечатано.</grad></shadow>",

    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>A Centipede\u200c will\u200c not attack you\u200c first. It\u200c uses the same\u200c anger\u200c system that Bees\u200c and Zombified Piglins use, which\u200c means it holds a\u200c grudge, and it does not hold it alone.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Сороконожка не нападёт на вас первой. Она использует ту же систему гнева, что и Пчёлы, и Зомбифицированные пиглины, а значит, она помнит обиду и не остаётся одна в своём гневе.</grad></shadow>",

    # ── enigmatic_charms ────────────────────────────────────────────────────
    "[!warn] At full\u200c health it does absolutely\u200c nothing. At\u200c one heart it\u200c is the\u200c strongest charm\u200c in\u200c the mod.":
    "[!warn] При полном здоровье он не делает абсолютно ничего. При одном сердце это самый сильный оберег в моде.",

    # ── hands ───────────────────────────────────────────────────────────────
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Drops from\u200c the </grad>"
    "<grad from=#E2683B to=#FFC0A8 f=0.8>Super Sniffer</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, the </grad>"
    "<grad from=#E2683B to=#FFC0A8 f=0.8>1500 health</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> boss\u200c you\u200c make by\u200c striking\u200c an ordinary sniffer with\u200c lightning.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Выпадает из </grad>"
    "<grad from=#E2683B to=#FFC0A8 f=0.8>Супер Нюхача</grad>"
    "<grad from=#FFFFFF to=#C7C7C7>, </grad>"
    "<grad from=#E2683B to=#FFC0A8 f=0.8>1500 здоровья</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> босса,\u200c которого вы создаёте,\u200c ударяя обычного нюхача молнией.</grad></shadow>",

    # ── reforging ──────────────────────────────────────────────────────────
    "[spoiler]Roughly 3% of armor\u200c rolls, 6% of weapon\u200c rolls, and\u200c somewhere between\u200c 9 and\u200c 11% of\u200c tool\u200c and shield\u200c rolls. Elytras and fishing rods\u200c do\u200c not get one, since\u200c they only\u200c have two\u200c modifiers\u200c each\u200c and a third\u200c would\u200c have made\u200c it\u200c a one in three chance.":
    "[spoiler]Примерно 3% брони, 6% оружия и где-то от 9 до 11% инструментов и щитов. Элитры и рыболовные удочки не получают его, ведь у них всего по два модификатора, а третий дал бы шанс один из трёх.",

    # ── supplementaries ────────────────────────────────────────────────────
    "When\u200c powered, the\u200c front (red) side of\u200c the Magnet will push blocks\u200c forward like a\u200c piston, whereas the\u200c back side will\u200c pull blocks\u200c towards\u200c it.":
    "При подаче питания передняя (красная) сторона Магнита выталкивает блоки вперёд, как поршень, а задняя тянет блоки к себе.",

    "If you put\u200c a banner\u200c inside a Glass\u200c Item\u200c Frame, it'll sit\u200c flat\u200c with the wall with\u200c the\u200c pattern that's in it, allowing\u200c you\u200c to create\u200c a\u200c wallpaper of sorts.":
    "Если поместить знамя внутрь Стеклянной рамки, оно прижмётся к стене вместе с рисунком на нём — так можно соорудить что-то вроде обоев.",

    "Shields\u200c display differently in Glass\u200c Item\u200c Frames, they sit flush\u200c with the\u200c wall and\u200c look\u200c nice.":
    "Щиты отображаются в Стеклянных рамках по-другому: они прилегают к стене вровень и выглядят красиво.",

    # ── create_new_age ──────────────────────────────────────────────────────
    "Reactor\u200c Glass is a\u200c stylish alternative\u200c to Reactor\u200c Casings, letting\u200c you\u200c see inside your\u200c nuclear\u200c setup without\u200c losing\u200c structural\u200c strength.":
    "Стекло реактора — стильная альтернатива Реакторному корпусу: видно начинку ядерной установки, и прочность конструкции при этом не теряется.",

    # ── Terramity: мусорные маркеры, модель переставила фразу ──────────────
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Terramity\u200c takes Minecraft\u200c past netherite and\u200c keeps going. New\u200c gems, new metals, five bosses, a pile of\u200c guns and\u200c more accessories than\u200c you\u200c will ever\u200c wear\u200c at once.</grad></shadow>":
    "<shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Terramity\u200c выводит Minecraft\u200c за пределы незерита и\u200c продолжает. Новые\u200c самоцветы, новые металлы, пять боссов, груда\u200c оружия и больше аксессуаров, чем вы\u200c когда-либо\u200c наденете\u200c разом.</grad></shadow>",

    # ── enigmatic_curses: предупреждение ──────────────────────────────────
    "[!warn] Think\u200c carefully. The\u200c safety net is\u200c the\u200c only thing\u200c standing\u200c between\u200c a bad\u200c spell rotation and\u200c instant death.":
    "[!warn] Думайте\u200c вдумчиво. Страховка — единственное, что\u200c стоит между вами и мгновенной смертью\u200c из-за неудачной\u200c ротации\u200c заклинаний.",

    # ── bosses: непереведённое имя босса ───────────────────────────────────
    "<grad from=#CC0000 to=#FF3333><pulse base=0.65 a=0.8 f=1.5><turb a=0.2 f=0.4><shake a=0.2 f=0.4>Redstone Monstrosity</shake></turb></pulse></grad>":
    "<grad from=#CC0000 to=#FF3333><pulse base=0.65 a=0.8 f=1.5><turb a=0.2 f=0.4><shake a=0.2 f=0.4>Краснокаменное чудовище</shake></turb></pulse></grad>",
}


def tags_of(text: str) -> list[str]:
    return RE_TAG.findall(text)


def main() -> None:
    p = WORK / "quests_ru.json"
    ru = json.loads(p.read_text(encoding="utf-8"))

    # ключи задаём по EN-строке; ищем её в словаре
    index: dict[str, str] = {}
    for en, ru_text in ru.items():
        index[en] = ru_text

    changed = 0
    missing = []
    bad = []
    for en, new_ru in FIXES.items():
        if en not in index:
            # EN-строка может отличаться невидимыми символами — ищем по нормализованному виду
            norm = en.replace("\u200c", "")
            hit = None
            for k in index:
                if k.replace("\u200c", "") == norm:
                    hit = k
                    break
            if hit is None:
                missing.append(en)
                continue
            en = hit
        if tags_of(en) != tags_of(new_ru):
            bad.append(en)
            continue
        if index[en] != new_ru:
            index[en] = new_ru
            changed += 1

    if missing:
        print(f"НЕ НАЙДЕНО в словаре: {len(missing)}")
        for m in missing:
            print("  ", m[:120])
    if bad:
        print(f"РАЗМЕТКА НЕ СОВПАЛА: {len(bad)}")
        for b in bad:
            print("  ", b[:120])
        return 1

    p.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"исправлено строк: {changed}")

    # контроль: в словаре не должно остаться мусорных маркеров
    left = sum(1 for v in index.values() if re.search(r"<x[^>]*>", v))
    print(f"осталось строк с мусором <x_N/>: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
