"""Ручные переводы для меню классов, подсказок и прочих конфигов сборки.

Зачем: переводчик (Google) даёт грамматически верный текст, но названия черт,
машин и характеристик в игре показываются по-английски (они зашиты в мод) —
переводить их значило бы расходиться с тем, что видит игрок. Здесь собраны
точные формулировки характеристик и правки прозы.

Термины, оставленные английскими (так же, как в игре):
  черты: Adaptive, Regenerating, Undying, Teleport, Incarceration, Split,
         Repelling, Corrosion, Erosion, Counter Strike, Drain, Killer Aura,
         Reflect, Dementor, Dispell, Ragnarok, Hostility, Arena, Tanky, Protected
"""

# ---------------------------------------------------------------------------
# Характеристики классов: точный перевод каждой строки
# ---------------------------------------------------------------------------

STATS = {
    "&6+10% Height": "&6+10% Рост",
    "&6+10% Size": "&6+10% Размер",
    "&6+10% Width": "&6+10% Ширина",
    "&6+20% Size": "&6+20% Размер",
    "&6+5% Width": "&6+5% Ширина",
    "&6-15% Height": "&6-15% Рост",
    "&6-20% Width": "&6-20% Ширина",
    "&6-30% Width": "&6-30% Ширина",
    "&7No stat changes": "&7Без изменений характеристик",
    "&a+1 Heart": "&a+1 сердце",
    "&a+1 Roll Charge": "&a+1 заряд кувырка",
    "&a+10% Critical Chance": "&a+10% Шанс критического удара",
    "&a+10% Healing Received": "&a+10% Получаемое исцеление",
    "&a+10% Life Steal": "&a+10% Похищение жизни",
    "&a+10% Max Health": "&a+10% Максимальное здоровье",
    "&a+10% Melee Damage": "&a+10% Урон в ближнем бою",
    "&a+10% Ranged Damage": "&a+10% Урон дальнего боя",
    "&a+10% Ranged Resistance": "&a+10% Сопротивление дальнему бою",
    "&a+10% Resistance": "&a+10% Сопротивление",
    "&a+10% Speed": "&a+10% Скорость",
    "&a+100 Max Mana (Iron's)": "&a+100 Макс Мана (Iron's)",
    "&a+100% Demon Will": "&a+100% Демоническая воля",
    "&a+100% Mining Speed": "&a+100% Скорость добычи",
    "&a+15% Cast Speed": "&a+15% Скорость применения заклинаний",
    "&a+15% Goety Soul Discount": "&a+15% Скидка душ Goety",
    "&a+15% Goety Spell Cooldown Reduction": "&a+15% Сокращение перезарядки заклинаний Goety",
    "&a+15% Melee Damage": "&a+15% Урон в ближнем бою",
    "&a+15% Minion Attack Speed": "&a+15% Скорость атаки прислужников",
    "&a+15% Speed": "&a+15% Скорость",
    "&a+150 Max Mana (Iron's)": "&a+150 Макс Мана (Iron's)",
    "&a+2 Ars Spell Damage": "&a+2 Заклинательный Урон Арс",
    "&a+2 Block Reach": "&a+2 Дальность взаимодействия",
    "&a+2 Hearts": "&a+2 сердца",
    "&a+2 Minion Slots": "&a+2 Слота для прислужников",
    "&a+2 Summon Damage (Ars)": "&a+2 Урон призыва (Ars)",
    "&a+20% Arrow Velocity": "&a+20% Скорость стрел",
    "&a+20% Dodge Chance": "&a+20% Шанс уклонения",
    "&a+20% Minion Movement Speed": "&a+20% Скорость движения прислужников",
    "&a+200 Max Mana (Ars)": "&a+200 Макс Мана (Ars)",
    "&a+25% Blood Spell Power": "&a+25% Сила кровавых заклинаний",
    "&a+25% Critical Damage": "&a+25% Критический урон",
    "&a+25% Holy Spell Power": "&a+25% Сила святых заклинаний",
    "&a+25% Melee Damage": "&a+25% Урон в ближнем бою",
    "&a+25% Minion Damage": "&a+25% Урон прислужников",
    "&a+25% Summon Damage on every servant you own": "&a+25% Урон призыва за каждого вашего слугу",
    "&a+25% Summon Damage on every summon you own": "&a+25% Урон призыва за каждое ваше призвание",
    "&a+25% Whip Range": "&a+25% Дальность хлыста",
    "&a+3 Hearts": "&a+3 сердца",
    "&a+3 Luck": "&a+3 Удача",
    "&a+30% Knockback Resistance": "&a+30% Сопротивление отбрасыванию",
    "&a+30% Ranged Damage": "&a+30% Урон дальнего боя",
    "&a+30% Spell Power": "&a+30% Сила заклинаний",
    "&a+4 Armor": "&a+4 Броня",
    "&a+40% Mining Speed": "&a+40% Скорость добычи",
    "&a+5 Hearts": "&a+5 сердец",
    "&a+5% Damage Reduction": "&a+5% Снижение урона",
    "&a+5% Speed": "&a+5% Скорость",
    "&a+50% Critical Damage": "&a+50% Критический урон",
    "&a+50% Draw Speed": "&a+50% Скорость натяжения тетивы",
    "&a+50% Eating Speed": "&a+50% Скорость еды",
    "&a+50% Fall Damage Reduction": "&a+50% Снижение урона от падения",
    "&a+50% Gun Damage": "&a+50% Урон огнестрельного оружия",
    "&a+50% Jump Height": "&a+50% Высота прыжка",
    "&a+50% Knockback Resistance": "&a+50% Сопротивление отбрасыванию",
    "&a+50% Minion Range": "&a+50% Дальность прислужников",
    "&a+50% Souls Gained": "&a+50% Получаемые души",
    "&a+500% Sacrifice LP": "&a+500% Приносимых очков жизни",
    "&a+6 Armor": "&a+6 Броня",
    "&a+7% Melee Damage": "&a+7% Урон в ближнем бою",
    "&a+7% Ranged Damage": "&a+7% Урон дальнего боя",
    "&a+7% Spell Power": "&a+7% Сила заклинаний",
    "&a+Necromancy tab at the Study Lectern": "&aВкладка «Некромантия» на Учебной кафедре",
    "&a-15% Roll Cooldown": "&a-15% Откат кувырка",
    "&a-20% Roll Cooldown": "&a-20% Откат кувырка",
    "&a1.5x shorter parry cooldown": "&aОткат парирования в 1,5 раза короче",
    "&a10% chance to deal 2.5x damage": "&a10% шанс нанести урон в 2,5 раза",
    "&a12 Inventory Rows": "&a12 рядов инвентаря",
    "&a5% chance on hit to Poison, Wither, Weaken, Slow or Blind for 5s":
        "&a5% шанс при попадании наложить Яд, Увядание, Слабость, Замедление или Слепоту на 5 с",
    "&aBare-hand parry from the start": "&aПарирование голыми руками с самого начала",
    "&aDeathblow: finish a staggered enemy under 30% health":
        "&aДобивание: добейте оглушённого врага, у которого меньше 30% здоровья",
    "&aProjectile parry from the start": "&aПарирование снарядов с самого начала",
    "&c+20% Ice Spell Damage Taken": "&c+20% Получаемый урон от ледяных заклинаний",
    "&c-1 Heart": "&c-1 сердце",
    "&c-1 Luck": "&c-1 Удача",
    "&c-10% Walking Speed": "&c-10% Скорость передвижения",
    "&c-100 Max Mana": "&c-100 Макс Мана",
    "&c-100% Fire and Holy Magic Resistance": "&c-100% Сопротивление огненной и святой магии",
    "&c-2 Hearts": "&c-2 сердца",
    "&c-2 Melee Damage": "&c-2 Урон в ближнем бою",
    "&c-20% Attack Damage": "&c-20% Урон при атаке",
    "&c-20% Max Mana": "&c-20% Макс Мана",
    "&c-20% Melee Damage": "&c-20% Урон в ближнем бою",
    "&c-20% Melee Resistance": "&c-20% Сопротивление ближнему бою",
    "&c-20% Other Spell Schools": "&c-20% Прочие школы магии",
    "&c-20% Ranged Damage": "&c-20% Урон дальнего боя",
    "&c-20% Ranged Resistance": "&c-20% Сопротивление дальнему бою",
    "&c-20% Swim Speed": "&c-20% Скорость плавания",
    "&c-25% Critical Damage": "&c-25% Критический урон",
    "&c-25% Fire Spell Power": "&c-25% Сила огненных заклинаний",
    "&c-25% Healing Received": "&c-25% Получаемое исцеление",
    "&c-25% Melee Damage": "&c-25% Урон в ближнем бою",
    "&c-25% Speed": "&c-25% Скорость",
    "&c-30% Melee Damage": "&c-30% Урон в ближнем бою",
    "&c-30% Ranged Damage": "&c-30% Урон дальнего боя",
    "&c-30% Spell Power": "&c-30% Сила заклинаний",
    "&c-4 Hearts": "&c-4 сердца",
    "&c-40% Attack Damage": "&c-40% Урон при атаке",
    "&c-5% Speed": "&c-5% Скорость",
    "&c-50% Holy Magic Resistance": "&c-50% Сопротивление святой магии",
    "&c-50% Mana Regen": "&c-50% Регенерация маны",
    "&c-50% Ranged Damage": "&c-50% Урон дальнего боя",
    "&c-50% Spell Power": "&c-50% Сила заклинаний",
    "&c-6 Armor": "&c-6 Броня",
    "&c-7 Luck": "&c-7 Удача",
    "&c5% chance to take 2x damage": "&c5% шанс получить двойной урон",
    "&cNo Mana": "&cНет маны",
}

# ---------------------------------------------------------------------------
# Правки прозы: названия черт и машин остаются английскими, как в игре
# ---------------------------------------------------------------------------

PROSE = {
    # --- черты враждебности ---
    "Hostility traits hit you half as hard: Reflect and Killer Aura deal half damage, "
    "harmful effects from Hostility last half as long.":
        "Черты враждебности бьют вдвое слабее: Reflect и Killer Aura наносят вдвое меньше урона, "
        "а вредные эффекты враждебности длятся вдвое меньше.",

    "&cKiller Aura&r ticks you down with magic damage.\nA &bRing of Divinity&r makes you immune to it.":
        "&cKiller Aura&r постепенно снимает ваше здоровье магическим уроном.\n"
        "&bКольцо Божественности&r делает вас невосприимчивым к нему.",

    "&cRagnarok&r seals your gear in the middle of a fight.\n"
    "A &6Pocket of Restoration&r unseals it while you keep swinging.":
        "&cRagnarok&r запечатывает ваше снаряжение посреди боя.\n"
        "&6Карман восстановления&r распечатывает его, пока вы продолжаете сражаться.",

    "&cDementor&r shrugs off weapons.\nKill it with &dmagic&r instead of steel.":
        "&cDementor&r отмахивается от оружия.\nУбейте его &dмагией&r, а не сталью.",

    "&cDispell&r shrugs off magic.\nSwitch to &ephysical weapons&r or an &6Imagine Breaker.":
        "&cDispell&r отмахивается от магии.\nПереключитесь на &eфизическое оружие&r или &6Imagine Breaker&r.",

    "&cAdaptive&r mobs learn the damage you use.\nRotate weapons, or lean on &apoison, wither and fire.":
        "&cAdaptive&r мобы запоминают, каким уроном вы бьёте.\n"
        "Чередуйте оружие или опирайтесь на &aяд, увядание и огонь&r.",

    "&cAdaptive&r only remembers your last few damage types.\n"
    "A wide kit outruns its memory. One sword does not.":
        "&cAdaptive&r помнит лишь несколько последних типов урона.\n"
        "Широкий набор обманывает его память. Один меч — нет.",

    "&cRegenerating&r or &cUndying&r mob refusing to stay dead?\n"
    "A &6Cursed Blade&r shuts down healing and revives.":
        "&cRegenerating&r или &cUndying&r моб не хочет умирать?\n"
        "&6Проклятый клинок&r отключает лечение и воскрешает.",

    "&cTeleport&r mobs blink out of your melee range.\nAn &eIncarceration&r effect pins them in place.":
        "&cTeleport&r мобы выскакивают из зоны ближнего боя.\n"
        "Эффект &eIncarceration&r придерживает их на месте.",

    "Tired of &cSplit&r mobs multiplying?\nPut &eSplit Suppressor&r on your weapon.":
        "Надоело, что &cSplit&r мобы множатся?\nНаденьте &eSplit Suppressor&r на оружие.",

    "&cRepelling&r mobs are immune to projectiles.\nPut the bow away and go &6melee.":
        "&cRepelling&r мобы невосприимчивы к снарядам.\nУберите лук и перейдите в &6ближний бой&r.",

    "&cCorrosion&r and &cErosion&r eat the gear you are wearing.\nFight them in &7spares&r or at &erange.":
        "&cCorrosion&r и &cErosion&r съедают ваше снаряжение.\n"
        "Сражайтесь с ними в &7запасном комплекте&r или &eиздалека&r.",

    "&cCounter Strike&r punishes you for holding attack.\nHit, step back, then hit again.":
        "&cCounter Strike&r наказывает за задержку атаки.\nУдарьте, отступите, затем ударите снова.",

    "&cDrain&r steals your buffs and feeds on your debuffs.\n"
    "A &bRing of Reflection&r throws them back at the mobs.":
        "&cDrain&r крадёт ваши положительные эффекты и питается отрицательными.\n"
        "&bКольцо Отражения&r отбрасывает их обратно в мобов.",

    "Cannot place blocks near a mob?\nThat is &cArena&r, and it ignores your pets. Hit it yourself.":
        "Нельзя ставить блоки рядом с мобом?\nЭто &cArena&r, и она игнорирует ваших питомцев. Бейте сами.",

    "&cProtected&r and &cTanky&r mobs shrug off raw numbers.\n"
    "&aDamage over time&r and true damage still land in full.":
        "&cProtected&r и &cTanky&r мобы не впечатляются голыми числами.\n"
        "&aУрон со временем&r и истинный урон всё равно проходят полностью.",

    "You deal 10% more damage to mobs with a Hostility level, and they drop 50% more Hostility loot "
    "when you kill them.":
        "Вы наносите на 10% больше урона мобам с уровнем Hostility, и при их убийстве они "
        "оставляют на 50% больше добычи Hostility.",

    # --- предметы и машины: имена как в игре ---
    "Prefer a magic or ranged playstyle?\nTry the &eRing Of The Seven Virtues!&r":
        "Предпочитаете магию или дальний бой?\nПопробуйте &eКольцо Семи Добродетелей!&r",

    "Equipping the &cRing of The Seven Curses&r\nforces you to use &cLP (Life Points)&r as mana.":
        "Надевание &cКольца Семи Проклятий&r\nзаставляет использовать &cLP (очки жизни)&r вместо маны.",

    "Going out at night with the &cRing Of The Seven Curses&r\nis a really, &creally bad idea.&r":
        "Выходить ночью с &cКольцом Семи Проклятий&r\n— &cочень, очень плохая идея.&r",

    "Holy spells recharge 25% faster, 40% while you wear the Ring of the Seven Virtues.":
        "Святые заклинания перезаряжаются на 25% быстрее, на 40% — пока вы носите "
        "Кольцо Семи Добродетелей.",

    "Healing past your max health isn't wasted. Every half second the extra turns into Holy damage "
    "on up to 6 mobs within 6 blocks, scaled by your holy spell power. Double while you wear "
    "the Ring of the Seven Virtues.":
        "Исцеление сверх максимального здоровья не пропадает. Каждые полсекунды излишек "
        "превращается в священный урон по 6 мобам в радиусе 6 блоков, в зависимости от силы "
        "ваших святых заклинаний. Пока вы носите Кольцо Семи Добродетелей — вдвое больше.",

    "&dEnchanting Infuser&r is a game-changer.\nCraft it as soon as you beat &cThe Wither!&r":
        "&dEnchanting Infuser&r меняет правила игры.\nСоздайте его сразу после победы над &cИссушителем&r.",

    "Struggling to fight the Wither?\nTrap him in a &eCompact Machine!&r":
        "Не получается победить Иссушителя?\nЗаманите его в &eCompact Machine&r!",

    "Want a &6Wither Force Field?&r\nKill the Wither with &eany projectile&r, not only arrows.":
        "Хотите &6Силовое поле Иссушителя&r?\nУбейте Иссушителя &eлюбым снарядом&r, а не только стрелами.",

    "The &dEnchanting Infuser&r is a game-changer.\n"
    "Craft it as soon as you beat &cThe Wither!&r":
        "&dEnchanting Infuser&r меняет правила игры.\n"
        "Создайте его сразу после победы над &cИссушителем&r.",

    # --- прочее ---
    "&a5% chance on hit to Poison, Wither, Weaken, Slow or Blind for 5s":
        "&a5% шанс при попадании наложить Яд, Увядание, Слабость, Замедление или Слепоту на 5 с",

    "&cDying&r hurts!\nYou will &close&r &e70% of your XP.&r":
        "&cСмерть&r больна!\nВы &cпотеряете&r &e70% своего опыта&r.",

    "&cDying a lot?&r\nStop face-tanking and try &adodging!&r":
        "&cЧасто умираете?&r\nХватит тупо принимать урон в лоб — попробуйте &aуворачиваться&r!",
}
