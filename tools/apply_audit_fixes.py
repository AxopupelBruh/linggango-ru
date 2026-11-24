# -*- coding: utf-8 -*-
"""Точечные правки перевода по итогам аудита (docs/АУДИТ_ПЕРЕВОДА_50_СТРОК.md).

Правится:
  * workspace/work/key_overrides.json — правки по ключу (применяются последними);
  * workspace/work/mods_ru.json      — глоссарий: убраны переведённые подстановки.
"""
import json, os, zipfile

WS = "/home/ax/Documents/Opencode/Для сборок переводов/linggango/workspace"
INST = "/home/ax/.local/share/gdlauncher_carbon/data/instances/Linggango/instance"

# ─────────────────────────────────────────────────────────────── tiered
# Названия предметов мода tiered. В паке вместо них стояло название редкости.
TIERED_NAMES = {
    "Stalwart": "Стойкий", "Fit": "Подогнанный", "Fleetstep": "Быстрый шаг",
    "Chilled": "Охлаждённый", "Brutal": "Жестокий", "Cruel": "Безжалостный",
    "Crumbling": "Разрушающий", "Piercing": "Пронзающий", "Fletched": "Пернатый",
    "Lightshot": "Лёгкий выстрел", "Agile": "Ловкий", "Brisk": "Быстрый",
    "Tempered": "Закалённый", "Extended": "Удлинённый", "Observant": "Внимательный",
    "Tectonic": "Тектонический", "Heart of the Titan": "Сердце Титана",
    "Riftstep": "Разломный шаг", "Winter's Abyss": "Бездна Зимы",
    "Immaculate": "Непорочный", "Storm Cleaver": "Грмовой Рассекатель",
    "Dread Cleaver": "Жуткий Рассекатель", "Citadel Crusher": "Дробилка Цитадели",
    "Fate Carver": "Резчик Судьбы", "Stormbite Quill": "Перо Грозового Укуса",
    "Tempest Arrow": "Стрела Бури", "Horizon Walker": "Ходок Горизонта",
    "Seismic Artisan": "Сейсмический Мастер",
    "Forgemaster's Blessing": "Благословение Кузнеца", "Titan's Arm": "Рука Титана",
    "Elder Insight": "Мудрость Старейшины", "Wall of Eternity": "Стена Вечности",
    "Ancient Pulse": "Древний Пульс", "Eclipse Runner": "Бегун Затмения",
    "Avatar of the Deep": "Аватар Глубин", "Flawless": "Безупречный",
    "Wrath of Ares": "Гнев Арея", "Sunfall": "Падение Солнца",
    "The Siege Eternal": "Вечная Осада", "The Final Opening": "Последнее Отверстие",
    "Skybreaker Quill": "Перо Небосколы", "Heaven's Streak": "Небесный След",
    "Trailblaze of Storms": "Первопроходец Гроз", "Primeval Dig": "Древняя Раскопка",
    "Indomitable Frame": "Непоколебимый Остов", "Grasp of Giants": "Хватка Исполинов",
    "Grand Savant": "Великий Мудрец", "World's Last Bastion": "Последний Бастион Мира",
    "Blood of Creation": "Кровь Сотворения",
    "Shadow of the Final Step": "Тень Последнего Шага",
    "Leviathan of the Frost": "Левиатан Инея", "Wrath of Creation": "Гнев Сотворения",
    "Judgement of Extinction": "Суд Вымирания", "Fall of all Bastions": "Падение Бастионов",
    "Silence Between Heartbeats": "Тишина Между Ударами Сердца",
    "Arrow of Creation's Edge": "Стрела Кромки Сотворения",
    "Flight Beyond Time": "Полёт За Пределами Времени",
    "Transcendent Velocity": "Трансцендентная Скорость",
    "Transcendant Velocity": "Трансцендентная Скорость",
    "Terra Sunderer": "Расщепитель Земли",
    "Relic of Infinite Use": "Реликвия Бесконечного Применения",
    "Hand of the Cosmic Delver": "Рука Космического Искателя",
    "Seer of All Paths": "Провидец Всех Путей", "Bastion-Born": "Рождённый Бастионом",
    "Blood-Forged": "Кованый Кровью", "Slipstride": "Скользящий Шаг",
    "Frostborn": "Рождённый Инеем", "Fury-Forged": "Кованый Яростью",
    "Shadow-Sunder": "Рассекающий Тень", "Anvil Breaker": "Наковальнолом",
    "Heart Piercer": "Пронзающий Сердце", "Hawkslayer": "Убийца Ястребов",
    "Cloud Piercer": "Пронзающий Облака", "Tempest Step": "Шаг Бури",
    "Vein Splitter": "Раскалывающий Жилы", "Adamant Hand": "Несокрушимая Рука",
    "Horizon Reach": "Дотягивающийся До Горизонта", "Enlightened": "Просветлённый",
    "Guarded": "Охраняемый", "Refined": "Утончённый", "Hearty": "Крепкий",
    "Rolling Wind": "Катящийся Ветер", "Icebound": "Скованный Льдом",
    "Predatory": "Хищный", "Warfang": "Боевой Клык", "Sunderer": "Рассекатель",
    "Vital Strike": "Жизненный Удар", "Barbed": "Зазубренный",
    "Wind-Bound": "Связанный Ветром", "Feather Step": "Перьевой Шаг",
    "Haste Forged": "Кованая Спешка", "Alloy Forged": "Кованый Сплав",
    "Farstrike": "Дальний Удар", "Scholar": "Учёный",
}

FIXES = {}


def add(ns, mapping):
    FIXES.setdefault(ns, {}).update(mapping)


# ── 8-18: подмена типа предмета ────────────────────────────────────────
add("bloodmagic", {
    "block.bloodmagic.dungeon_metal": "Адский блок",
    # 21: битый якорь ссылки
    "guide.patchouli.bloodmagic.ritual_info.awakened_activation_crystal_link":
        "$(l:bloodmagic:rituals/activation_crystals#awakened)%s$(/l)",
    # 22: переведён макрос переноса строки
    "guide.patchouli.bloodmagic.ritual_info.counter_formatter": "$(br)%s%s$()",
})
add("cataclysm", {
    "key.cataclysm.chestplate_ability": "Способности нагрудника Cataclysm",
})
add("mysticalagriculture", {
    "item.mysticalagriculture.imperium_boots": "Империевые сапоги",
    "item.mysticalagriculture.prudentium_boots": "Прудентиевые сапоги",
    "block.mysticalagriculture.soulstone_cobble_stairs": "Булыжниковые ступени из камня душ",
})
add("terramity", {
    "item.terramity.sapphire_armor_chestplate": "Сапфировый нагрудник",
    "block.terramity.void_tile_slab": "Ступени из пустотной плитки",
})
add("armageddon_mod", {
    "block.armageddon_mod.mossy_helionite_bricks_slab": "§6Мшистая плита из гелионитового кирпича",
    # 39: §-код цвета съел цифру
    "item.armageddon_mod.the_sword_of_the_starved.description_7":
        " §7Когда у существа есть §9голод, §7наносит §920% §7дополнительного урона",
    # 47: Speed II переведён как Jump Boost
    "item.armageddon_mod.apprentice_builder_armor_boots.description_3": "§9Скорость II",
})
add("somemoreblocks", {
    "block.somemoreblocks.mossy_end_stone_brick_stairs": "Ступени из замшелых эндерняковых кирпичей",
})
add("mutantmonsters", {
    "item.mutantmonsters.creeper_shard": "Осколок крипера",
})
add("alexscaves", {
    "entity.alexscaves.magnetic_weapon": "Магнитное оружие",
})

# ── 23: переведён макрос очистки ────────────────────────────────────────
add("enigmaticlegacy", {
    "book.enigmaticlegacy.entry.sharpshooter_enchantment.page.1":
        "Одно из возможных чар для арбалета, одно из самых полезных.<br2/>Оно увеличивает урон, "
        "наносимый стрелами из арбалета, что в чем-то похоже на Силу луков. Точнее, за каждый уровень "
        "Меткийа стрелок базовый урон арбалета будет увеличиваться на <&l>+40%%$(clear).",
})

# ── 24: испорчен синтаксис фильтра ─────────────────────────────────────
add("createlazytick", {
    "createlazytick.error.filter_empty_hint":
        "Никакого фильтра не было. Пример формата: {name:mechanical_saw,value>50}. "
        "Если внутри фигурных скобок есть пробелы, заключите весь фильтр в дополнительную "
        "пару двойных кавычек.",
})

# ── 33-35: потерянные числа ────────────────────────────────────────────
add("entity_texture_features", {
    "config.entity_texture_features.blink_frequency.tooltip":
        "Задаёт частоту случайного мерцания текстур. \n"
        " При значении 100 мобы мерцают случайным образом после \n"
        " задержки в 1 секунду, а затем через случайный промежуток от \n"
        " 1 до 100 тактов (0-5 секунд). \n"
        " Это можно задать / переопределить для каждого моба \n"
        " через ресурспак. \n"
        " Подробности — на странице загрузки мода.",
    "config.entity_texture_features.blink_length.tooltip":
        "Задаёт длительность мерцания текстур. \n"
        " 0 = 1 такт, 19 = 20 тактов / 1 секунда \n"
        " Это можно задать / переопределить для каждого моба \n"
        " через ресурспак. \n"
        " Подробности — на странице загрузки мода.",
    "config.entity_texture_features.skin_features_enable_full_transparency.tooltip":
        "Позволяет сделать скины игроков полностью прозрачными (100%). \n"
        " ВНИМАНИЕ: это перекрывает проверку прозрачности в 60% \n"
        " для скинов игроков, так что они могут стать полностью невидимыми. \n"
        " Эта опция меняет только то, что видите вы, \n"
        " и не делает вас невидимыми для других — это ради веселья. \n"
        " //ТРЕБУЕТСЯ ПЕРЕЗАПУСК\\\\",
})

# ── 37: зачарование «Защита» (перевод от DeepL, адаптирован) ───────────
add("l2complements", {
    "enchantment.l2complements.safeguard.desc":
        "Если прочность предмета превышает 1, при повреждении он сохранит как минимум 1 единицу прочности.",
})

# ── 40: Quartz Block переведён в «книжную полку» ───────────────────────
add("animus", {
    "jei.animus.imperfect_ritual_stone.reduction":
        "§6Ритуал редукции§r: Поставьте сверху блок кварца. Стоимость: 1000 LP. "
        "Убирает метку усиления с предмета в основной руке, возвращая уровни зачарований к норме.",
})

# ── 41-43, 45-46: обрыв текста ─────────────────────────────────────────
add("goety", {
    "info.goety.ice_axe": "Ломает ледяные блоки и роняет их.",
})
add("starcatcher", {
    "gui.guide.page.4.right.7": "Крючки, поплавки и приманки.",
    "gui.guide.page.0.right.17": "драгоценная <sclegendary>легендарная</sclegendary> рыба",
    "gui.guide.page.8.right.8": "в <sclegendary>легендарном</sclegendary> письме, поместите его внутрь",
})
add("terramity", {
    "advancements.angel_feather_advancement.descr": "Убейте ангела и соберите его перья.",
})
add("too_many_bows", {
    "item.too_many_bows.wind_bow.tooltip.ability":
        "Способность: §bПорыв бури§r \n"
        "  • При попадании выпускает порыв ветра \n"
        "  • Отбрасывает врагов рядом \n"
        "  • Прямые попадания наносят небольшой магический урон",
})

# ── 48-50: перевод приклеен к чужому ключу ────────────────────────────
add("bosses_of_mass_destruction", {
    "text.autoconfig.bosses_of_mass_destruction.option.gauntletConfig.attack": "Урон атаки",
    "text.autoconfig.bosses_of_mass_destruction.option.obsidilithConfig.attack": "Урон атаки",
    "text.autoconfig.bosses_of_mass_destruction.option.voidBlossomConfig.attack": "Урон атаки",
})
add("somakespells", {
    "effect.somakespells.blood_cut": "Кровавый порез",
    "spell.somakespells.blood_cut": "Кровавый порез",
})
add("morerelics", {
    "tooltip.relics.crown_of_the_legend.ability.never_die.stat.potency.value": "%1$s",
})

# ── потеряны подсказки клавиш ──────────────────────────────────────────
add("ars_nouveau", {
    "ars_nouveau.page3.spell_casting":
        "Если вы хотите привязать заклинание к другой вкладке, выберите вкладку справа "
        "и повторите описанный выше процесс. Предоставлено несколько сочетаний клавиш: "
        "$(k:ars_nouveau.next_slot), $(k:ars_nouveau.previous_slot), "
        "$(k:ars_nouveau.open_book), $(k:ars_nouveau.selection_hud).",
})

# ───────────────────────────────────── industrialforegoing: полный ремонт
# Подстановки в фигурных скобках — это названия предметов и действий.
# Их имя переводить НЕЛЬЗЯ: мод подставляет туда свои ключи.
add("industrialforegoing", {
    "text.industrialforegoing.book.animal_growth_increaser":
        "При подаче энергии и корма {breeding} будет кормить детёнышей животных, чтобы они {grow} быстрее.",
    "text.industrialforegoing.book.animal_independence_selector":
        "При подаче энергии перемещает животных {baby} с задней стороны на переднюю.@L@@L@"
        "Если установлен {Adult Filter}, он перемещает взрослых животных вместо детёнышей.",
    "text.industrialforegoing.book.animal_resource_harvester":
        "При подаче энергии взаимодействует с животными с помощью {buckets} и {shears}, "
        "чтобы доить коров и стричь овец.@L@@L@Также добывает {ink sacks} из кальмаров.",
    "text.industrialforegoing.book.biofuel_generator":
        "Вырабатывает энергию при подаче биотоплива. {bucket} биотоплива выдаёт 160RF/t, "
        "всего {640,000}RF. От одного {Bioreactor} можно запустить около {28} генераторов.",
    "text.industrialforegoing.book.bioreactor":
        "При подаче {power} и {bio materials} производит {biofuel}.@L@@L@"
        "Каждый предмет повышает эффективность всех предметов на {10}mb; при максимальной "
        "эффективности реактор выдаёт {1440}mb, потребляя {9} разных предметов.",
    "text.industrialforegoing.book.black_hole_controller":
        "Вмещает 9 {Black Hole Units} и даёт доступ к их содержимому. "
        "Это значит 9 × {2,147,483,647} предметов.",
    "text.industrialforegoing.book.block_destroyer":
        "При подаче энергии {break} любой блок перед собой и перемещает его в свой инвентарь.",
    "text.industrialforegoing.book.block_placer":
        "При подаче энергии {place} перед собой блоки из своего инвентаря.",
    "text.industrialforegoing.book.conveyor_upgrade_dropping":
        "Улучшение сбрасывания ставится в центральную часть конвейера: оно {drop} существ прямо "
        "под собой или отправляет предметы в инвентари под ним.@L@@L@"
        "У него есть {filter} с белым или чёрным списком; мобов можно фильтровать с помощью "
        "{Mob Imprisonment Tool} с помещённой внутрь сущностью.",
    "text.industrialforegoing.book.crop_enrich_material_injector":
        "При подаче энергии и удобрения удобряет посевы и саженцы костной мукой.@L@@L@"
        "Поддерживаемые удобрения: {bonemeal}, {Industrial Foregoing's} и {Forestry} удобрения.",
    "text.industrialforegoing.book.crop_recolector":
        "При подаче энергии {harvest} полностью выросшие посевы и срубает деревья, включая тыквы, "
        "арбузы и адский нарост. Каждая операция даёт немного {sludge} — его можно переработать "
        "в {Sludge Refiner} и получить материалы. (Заполненный бак {not} замедляет машину)",
    "text.industrialforegoing.book.crop_sower":
        "Сажает семена и саженцы — собирает их {Plant Gatherer}. Слоты можно {lock}, нажав на замок, "
        "тогда он будет {filter} входные предметы.@L@@L@"
        "{colored} фон обозначает цветные детали в {top} блока.",
    "text.industrialforegoing.book.fluid_crafter":
        "{fluid crafter} крафтит всё, что требует {one} типа жидкости, вместо использования "
        "{buckets} из рецепта. Чтобы это работало, положите предметы в сетку и {lock it}. "
        "После этого подавайте предметы в сетку, а жидкость — в бак.@L@@L@"
        "Если в рецепте нужно много одного предмета, используйте {Item Splitter}.",
    "text.industrialforegoing.book.fluid_pump":
        "Установленная над жидкостью Fluid Pump берёт эту жидкость как {filter} и начинает "
        "высасывать все жидкости того же типа в рабочей области — она ищет все жидкости {below} "
        "жидкостей рабочей области и высасывает их тоже. @L@@L@"
        "Вся выкачанная жидкость заменяется на {cobblestone}.",
    "text.industrialforegoing.book.fortune_addon":
        "Добавляет {fortune/looting} машинам, поддерживающим это дополнение. Его нужно зачаровать "
        "на {Fortune}, и уровень чар будет применяться к действиям машины.",
    "text.industrialforegoing.book.froster":
        "Froster позволяет создавать холодные вещества: он раскручивает поданную {water} "
        "на очень большой скорости и снижает температуру за счёт {power}.",
    "text.industrialforegoing.book.infinity_drill":
        "Мощный бур, потерявший всю свою энергию. Зарядив его, можно разрушать миры быстрее. "
        "Чем больше энергии, тем больше область выемки. Чтобы сохранить эту энергию, он может "
        "эффективнее расходовать {Biofuel}. Shift+ПКМ по нему меняет область выемки. @L@@L@"
        "{Он хранит секреты, которые легко доступны патронам и некоторым редким мобам в мире.}",
    "text.industrialforegoing.book.item_splitter":
        "{split} заданный размер стака по каждому слоту с разрешённой стороны {output}.",
    "text.industrialforegoing.book.meat_feeder":
        "Если Meat Feeder лежит в вашем {inventory} и в нём есть {Liquid Meat}, "
        "он автоматически {feed} вас.@L@@L@Работает как обычный контейнер для жидкости.",
    "text.industrialforegoing.book.mob_duplicator":
        "При подаче энергии, {Essence} и любой сущности в {Mob Imprisonment Tool} "
        "он создаёт их вокруг себя.@L@@L@Он {count} сущностей рядом и прекращает создавать их, "
        "если их слишком много.",
    "text.industrialforegoing.book.mob_imprisonment_tool":
        "Если нажать по сущности с этим предметом в руке, он {hold} сущность внутри себя.",
    "text.industrialforegoing.book.mob_relocator":
        "При подаче энергии {kill} любую сущность перед собой, как это сделал бы игрок.@L@@L@"
        "Он {collect} выпавшие предметы и превращает сферы опыта в {Essence}\". "
        "При наличии {Adult Filter Addon} убивает только взрослых мобов.",
    "text.industrialforegoing.book.oredictionary_converter":
        "Превращает предметы с одинаковой записью {oredicted} в отфильтрованный предмет.",
    "text.industrialforegoing.book.ore_fermenter":
        "При подаче {raw ore meat} он перерабатывается в {fermented ore meat} и увеличивается "
        "в размере. Снизу нужен {hot source}(горячие жидкости, огонь, магма-блоки), "
        "с любой другой стороны — {cold fluid}(холодные жидкости, лёд, ...).",
    "text.industrialforegoing.book.ore_processor":
        "Разбирает руды с {Silk Touched} на их дроп.@L@@L@"
        "Если подать {Essence}, будет разбирать их с удачей.",
    "text.industrialforegoing.book.ore_sieve":
        "При подаче {fermented ore meat} и небольшого количества {sand} отделяет руду от мяса "
        "и превращает её в {dust}.",
    "text.industrialforegoing.book.ore_washer":
        "При подаче {liquid meat} и {ore} отмывает кусочки руды мясом в {raw ore meat} "
        "для дальнейшей переработки.",
    "text.industrialforegoing.book.pink_slime":
        "Можно получить, убив {Pink Slime}, который появляется при размещении {Pink Slime Fluid} в мире.",
    "text.industrialforegoing.book.pitiful_fuel_generator":
        "Работает так же, как Petrified Fuel Generator, но принимает только {wood}.",
    "text.industrialforegoing.book.plant_interactor":
        "При подаче энергии {right click} по посевам и фруктам, собирая их в свой инвентарь "
        "или выбрасывая на землю, если они не помещаются. @L@@L@"
        "{*По умолчанию работает с Pam's Fruits and Plants.}",
    "text.industrialforegoing.book.potion_enervator":
        "При подаче энергии работает как улучшенная версия {brewing stand}.@L@@L@"
        "Сначала нужно {fill} стеклянные бутылки водой, затем {brewing} все ингредиенты "
        "в верхнем ряду в {order}, слева направо.@L@@L@"
        "Смотрите на {arrow}, чтобы видеть текущую операцию.",
    "text.industrialforegoing.book.protein_generator":
        "Вырабатывает энергию при подаче протеина. {bucket} протеина выдаёт 320RF/t, "
        "всего {1,280,000}RF.",
    "text.industrialforegoing.book.protein_reactor":
        "При подаче {power} и {some animals drops} производит {protein}.@L@@L@"
        "Каждый предмет повышает эффективность всех предметов на {10}mb; при максимальной "
        "эффективности реактор выдаёт {1440}mb, потребляя {9} разных предметов.",
    "text.industrialforegoing.book.range_addon":
        "Увеличивает рабочий {range} некоторых машин. Не все машины принимают это дополнение.",
    "text.industrialforegoing.book.sewer":
        "При подаче энергии собирает {Sewage} из животных сверху.",
    "text.industrialforegoing.book.sludge_refiner":
        "При подаче энергии и {1} ведра грязи (получено в сборщике растений) производит "
        "{earth like} материалы.@L@@L@{Если установлен JEI, посмотрите применения "
        "Sludge Refiner, чтобы узнать шанс выхода материалов}.",
    "text.industrialforegoing.book.straw":
        "Позволяет {drink} из жидкостей мира или баков. В зависимости от жидкости может давать "
        "разные {effects}.@L@@L@@L@@L@@L@(Я не отвечаю за вредные эффекты, которые может вызвать трубочка)",
    "text.industrialforegoing.book.tree_fluid_extractor":
        "Установленный перед любым {log} он производит {Liquid Latex}.@L@@L@"
        "Он медленно {consume} бревно, и каждый извлекатель жидкости из дерева ускоряет этот процесс.",
    "text.industrialforegoing.book.upgrades":
        "В Industrial Foregoing нет улучшений скорости, но можно использовать {Energy Upgrades} "
        "и {Speed Upgrades} из Tesla Core Lib, чтобы ускорить машины. Для установки следующего "
        "нужен предыдущий тир.",
    "text.industrialforegoing.book.villager_trade_exchanger":
        "При подаче энергии и {Mob Imprisonent Tool} с {Villager} внутри даёт доступ к автоматической "
        "торговле с этим жителем.",
    "text.industrialforegoing.book.water_resources_collector":
        "Установленный над бассейном воды {3x3} он автоматически {fish}.",
})


def main():
    ko_path = os.path.join(WS, "work", "key_overrides.json")
    ko = json.load(open(ko_path, encoding="utf-8"))

    added = 0
    for ns, d in FIXES.items():
        for k, v in d.items():
            if ko.setdefault(ns, {}).get(k) != v:
                ko[ns][k] = v
                added += 1

    # ── tiered: имена предметов ────────────────────────────────────────
    with zipfile.ZipFile(os.path.join(INST, "mods", "linggango_tweaks-7.47.jar")) as z:
        en_tiered = json.loads(z.read("assets/tiered/lang/en_us.json").decode("utf-8"))
    RAR = {"Обычный", "Необычный", "Редкий", "Эпический", "Легендарный",
           "Мифический", "Безупречный", "Изысканный"}
    with zipfile.ZipFile(os.path.join(INST, "resourcepacks", "zz_linggango_ru.zip")) as z:
        pack_tiered = json.loads(z.read("assets/tiered/lang/ru_ru.json").decode("utf-8"))
    tiered_fixed = 0
    for k, v in pack_tiered.items():
        if not k.startswith("tiered:") or v not in RAR:
            continue
        name = en_tiered.get(k)
        if not name or name not in TIERED_NAMES:
            continue          # у мода нет английского названия — ничего не выдумываем
        ko.setdefault("tiered", {})[k] = TIERED_NAMES[name]
        tiered_fixed += 1

    json.dump(ko, open(ko_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"key_overrides: добавлено/обновлено {added} строк, tiered — {tiered_fixed}")

    # ── глоссарий: убрать переведённые подстановки ──────────────────────
    g_path = os.path.join(WS, "work", "mods_ru.json")
    g = json.load(open(g_path, encoding="utf-8"))
    g_fixed = 0
    for en, ru in list(g.items()):
        if not isinstance(ru, str):
            continue
        new = ru.replace("{имя}", "{name}")
        new = new.replace("{name:mechanical_saw,значение>50}", "{name:mechanical_saw,value>50}")
        if new != ru:
            g[en] = new
            g_fixed += 1
    json.dump(g, open(g_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"глоссарий: исправлено {g_fixed} записей")


if __name__ == "__main__":
    main()
