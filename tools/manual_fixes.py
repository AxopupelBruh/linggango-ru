"""Ручные переводы названий и фраз, которые переводчик оставил на английском.

Сюда попадают:
  * названия предметов/машин, у которых есть устоявшийся русский вариант;
  * английские фразы в заголовках глав;
  * названия модов и шуточные строки — их НЕ трогаем (словарь приведён явно).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"

# ключ — внутренний текст (без тегов), значение — перевод
MANUAL = {
    # --- названия предметов и машин ---
    "Diamond Press": "Пресс для алмазов",
    "Frame Perfect": "Идеальный кадр",
    "Mekanism Farms": "Фермы Mekanism",
    "Iron's: Legendary Ink": "Iron's: Легендарные чернила",
    "AE2: MEGA Cells": "AE2: MEGA-накопители",
    "AE2: 4M Cells": "AE2: 4M-накопители",
    "Ad Astra: Glacio": "Ad Astra: Глацио",
    "Ars Nouveau: Apparatus": "Ар Нуво: Аппарат",
    "Ultra Sniffer": "Ультра-нюхатель",
    "Inscriber Logic Press": "Логический пресс вырезателя",
    "Certus Quartz": "Истинный кварц",
    "Fluix": "Флюикс",
    "Smart Cable": "Умный кабель",
    "ME Export Bus": "Экспортная шина ME",
    "MEGA Crafting": "MEGA-крафт",
    "ME Extended Drive": "Расширенный диск ME",
    "Extended Inscriber": "Расширенный вырезатель",
    "Bloomberry": "Блумберри",
    "Bloomlight": "Блумлайт",
    "Bio-Forge": "Био-кузница",
    "Bio-Lab": "Био-лаборатория",
    "Chrysalis": "Хризалис",
    "Beyond The Mod": "За пределами мода",
    "Ancient Fiber": "Древнее волокно",
    "Amethyst Gear": "Аметистовая шестерёнка",
    "Echoium Nugget": "Слиток эхоиума",
    "Stoves Connect": "Соединение печей",
    "Bluetooth": "Блютуз",
    "Redstone++": "Редстоун++",
    "The One Box": "Единственная коробка",
    "Aureal Fueling": "Топливо ауреума",
    "Geo Conductor": "Геопроводник",
    "Seismic Surf": "Сейсмический сёрфинг",
    "Rock Launch": "Бросок камня",
    "Deepdark Vermin": "Глубоконёчные твари",
    "Access Focus": "Фокус доступа",
    "Ignite": "Воспламенение",
    "Sonic Boom": "Звуковой удар",
    "Desert Crush": "Сокрушение пустыни",
    "Blizzard": "Буря",
    "Guardian": "Страж",
    "Stellar": "Звёздный",
    "Dark Tools": "Тёмные инструменты",
    "XP vacuum": "Вакуум опыта",
    "Soul Thrift": "Бережливость души",
    "Sabbath Engine": "Двигатель Саббат",
    "Recall Focus": "Фокус воспоминания",
    "Animation Core": "Ядро анимации",
    "Spores Recreator": "Воссоздатель спор",
    "Fluid Placer": "Разместитель жидкости",
    "Infinity Gear": "Бесконечная шестерёнка",
    "Infinity Launcher": "Бесконечный пусковой механизм",
    "Infinity Nuke": "Бесконечная ядерная бомба",
    "Primogel Goo": "Примогелевая слизь",
    "Ferricore Tools": "Инструменты из феррокора",
    "Goo Soil": "Почва слизи",
    "Celestigem Tools": "Инструменты из целестигема",
    "Shadowpulse Goo": "Слизь теневого импульса",
    "Rampage Clock": "Часы буйства",
    "Exodic": "Экзодический",
    "Deathsaw": "Пила смерти",
    "Papercut": "Бумажный порез",
    "Foreign Hook": "Иностранный крюк",
    "Powah: Nitro": "Поваа: Нитро",
    "Advanced Energy Cube": "Продвинутый энергетический куб",
    "Ultimate Energy Cube": "Высший энергетический куб",
    "Ultimate Mechanical Pipe": "Высшая механическая труба",
    "Elite Machinery": "Элитные механизмы",
    "Ultimate Machinery": "Высшие механизмы",
    "Elite Factory": "Элитная фабрика",
    "Ultimate Factory": "Высшая фабрика",
    "Chargepad": "Зарядная панель",
    "Pew": "Пиу",
    "Ultimate Personal Barrel": "Высший личный бочонок",
    "Better Gold": "Улучшенное золото",
    "Better Gold Tools": "Улучшенные золотые инструменты",
    "Quantum Universal Cable": "Квантовый универсальный кабель",
    "Jetpack": "Реактивный ранец",
    "Seismic Reader": "Сейсмический считыватель",
    "Osmium Tools": "Осмиевые инструменты",
    "Paxel": "Паксель",
    "QIO Importer": "Импортёр QIO",
    "Supremium Essence": "Супремиумная эссенция",
    "Cognizant Dust": "Познающая пыль",
    "Vanilla Automation": "Ванильная автоматизация",
    "AE2 Automation": "Автоматизация AE2",
    "Apex Crux": "Эпекс Крукс",
    "Magiblade": "Магический клинок",
    "Tidebreaker": "Пробивающий прилив",
    "Lustrous Moxie": "Сияющая Мокси",
    "Ribboncleaver": "Ленторез",
    "Dawnquiver": "Колчан рассвета",
    "Bloody Unique Cache": "Кровавый уникальный тайник",
    "Caelestis": "Каэлестис",
    "Limited Barrel I": "Ограниченная бочка I",
    "Limited Barrel II": "Ограниченная бочка II",
    "Limited Barrel III": "Ограниченная бочка III",
    "Limited Barrel IV": "Ограниченная бочка IV",
    "Chord Blast": "Аккордовый взрыв",
    "Well Fed": "Сыт",
    "Psy Fly": "Пси-муха",
    "Olympus": "Олимп",
    "5000 Magnum": "5000 Магнум",
    "The Everyday Buffs": "Обычные усиления",
    "Sinfire Embrace": "Объятие синего огня",
    "Ruby": "Рубин",
}

# строки с префиксом/суффиксом OneBarrel / OneDrive
RE_ONEBARREL = re.compile(r"\bOne(Barrel|Drive)\b")

# полные переводы строк (используются как есть)
FULL = {
    # в английской книге сборки остался китайский текст
    "单次召唤的仆从数量翻倍。": "Удваивает количество призванных слуг за один раз.",
    "Mobs with this trait can damage equipments, especially when equipments have high durability."
    "$(br2)It only appears at very high level, so don't worry too much.":
        "Мобы с этой чертой могут повреждать снаряжение, особенно если у него высокая прочность."
        "$(br2)Она встречается только на очень высоком уровне, так что не слишком беспокойтесь.",
    "To deal with mobs with this trait, make sure you have ways to restore or preserve durability "
    "for your equipments, such as Hardened or Life Mending.$(br2)You can also use Life Mending "
    "with Safeguard, which saves your equipments under most circumstances.":
        "Чтобы бороться с мобами этой чертой, убедитесь, что у вас есть способы восстанавливать "
        "или сохранять прочность снаряжения — например, «Окалённость» или «Похищение жизни».$(br2)"
        "Также можно использовать «Похищение жизни» вместе с «Защитой», которая почти всегда "
        "спасает ваше снаряжение.",
    "Smart Filters are a group of filter items, which can be placed in any module's filter slots "
    "instead of a normal item, and provide more sophisticated item matching features.":
        "Умные фильтры — это группа предметов-фильтров, которые можно поместить в слоты фильтра "
        "любого модуля вместо обычного предмета. Они умеют подбирать предметы по более сложным "
        "условиям.",
    # строки, которые переводчик оставил на английском (теги мешают разбору)
    "- <shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Each assembly holds </grad>"
    "<grad from=#8FE33F to=#DCFFA8 f=0.8>8,000</grad>"
    "<grad from=#FFFFFF to=#C7C7C7> fuel.</grad></shadow>":
        "- <shadow a=0.3><grad from=#FFFFFF to=#C7C7C7>Каждая сборка удерживает </grad>"
        "<grad from=#8FE33F to=#DCFFA8 f=0.8>8 000</grad>"
        "<grad from=#FFFFFF to=#C7C7C7> топлива.</grad></shadow>",
    "&e&lUltimate\u200c Loot Fabricator V4&r":
        "&e&lСовершенный производитель добычи V4&r",
    "&e&lUltimate Loot\u200c Fabricator\u200c V2&r":
        "&e&lСовершенный производитель добычи V2&r",
    "&e&lUltimate Loot\u200c Fabricator\u200c V3&r":
        "&e&lСовершенный производитель добычи V3&r",
    "### &e&lUltimate\u200c Loot Fabricator\u200c V1&r":
        "### &e&lСовершенный производитель добычи V1&r",
}


def apply_manual(source: str) -> int:
    """Применяет ручные переводы к файлу work/<source>_ru.json."""
    path = WORK / f"{source}_ru.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0

    # 1. точные совпадения по внутреннему тексту
    for key in list(data):
        if key in FULL:
            if data[key] != FULL[key]:
                data[key] = FULL[key]
                changed += 1
            continue
        text = key
        m = re.search(r">([^<>]*)</", text)
        inner = m.group(1) if m else text
        if inner in MANUAL:
            new_inner = MANUAL[inner]
            new_text = text.replace(inner, new_inner, 1)
            if new_text != data[key]:
                data[key] = new_text
                changed += 1
                continue
        # 2. OneBarrel / OneDrive
        if RE_ONEBARREL.search(text):
            new_text = RE_ONEBARREL.sub(
                lambda m: "ОднаБочка" if m.group(1) == "Barrel" else "ОдноХранилище", text)
            if new_text != data[key]:
                data[key] = new_text
                changed += 1

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return changed


if __name__ == "__main__":
    for src in (sys.argv[1:] or ["quests"]):
        n = apply_manual(src)
        print(f"{src}: применено ручных переводов — {n}")
