"""Правки имён классов и описаний (после вычитки игроком).

Замечания:
  * «наводчик» было с маленькой буквы и звучало калькой с «gunner»;
  * «Игрок» (Gambler) — слишком общо: игрок в игре и так игрок;
  * «Мул» (Mule) — звучит как животное, а не про перенос вещей;
  * остальные имена сверены с английским оригиналом и оставлены:
    Ironclad → Броненосец, Vanguard → Авангард, Pathfinder → Следопыт.
Описания вычитаны на предмет смешения «ты/вы» и неуклюжих конструкций.
"""

CLASS_NAMES = {
    "Berserker": "Берсеркер",
    "The Chosen One": "Избранный",
    "Deflector": "Дефлектор",
    "Dragon Rider": "Драконий всадник",
    "Gambler": "Картежник",
    "Gunner": "Стрелок",
    "Steampunk Machinist": "Стимпанк-механик",
    "Miner": "Шахтёр",
    "Monk": "Монах",
    "Necromancer": "Некромант",
    "Civilian": "Гражданский",
    "North Mage": "Северный маг",
    "Mule": "Вьючный мул",
    "Puppeteer": "Кукловод",
    "Pathfinder": "Следопыт",
    "Saint": "Святой",
    "&4&lScum": "&4&lОтбросы",
    "South Mage": "Южный маг",
    "Ironclad": "Броненосец",
    "Vampire": "Вампир",
    "Vanguard": "Авангард",
}

CLASS_DESCRIPTIONS = {
    "A beast of pure willpower. You care little for strategy, only for the thrill of the hunt.":
        "Зверь чистой силы воли. Вам мало заботит стратегия — только азарт охоты.",
    "Chaos picked you. Hunt what it sends, and take what it drops.":
        "Хаос выбрал тебя. Охотьтесь за тем, что он посылает, и забирайте то, что он роняет.",
    "You gave up the trade of blows. Nothing lands that you do not let land.":
        "Вы отказались от прямого боя. Ничто не падает, если вы этого не допустите.",
    "On foot you are just another fighter. In the saddle, you and your mount fight as one.":
        "Пешком вы — ещё один боец. В седле вы и ваш скакун сражаетесь как одно целое.",
    "Will fortune favor you?":
        "Будет ли удача к вам благосклонна?",
    "A sharpshooter who relies on gunpowder rather than bows.":
        "Снайпер, полагающийся на порох, а не на лук.",
    "You see the world as a machine, and you have the wrench to automate it.":
        "Вы смотрите на мир как на механизм — и у вас есть гаечный ключ, чтобы его автоматизировать.",
    "You prefer the isolation of the underground, far from the noise of the surface.":
        "Вы предпочитаете одиночество под землёй, вдали от шума поверхности.",
    "Your body is the only weapon you need. Peace comes from within.":
        "Ваше тело — единственное оружие, которое вам нужно. Покой приходит изнутри.",
    "The dead are not gone. They are waiting for someone to give them orders.":
        "Мёртвые не ушли. Они ждут, что кто-то отдаст им приказ.",
    "You are nobody.":
        "Ты — никто.",
    "You create your own magic; the only thing that can stop you is your own imagination.":
        "Вы творите собственную магию. Остановить вас может только ваше воображение.",
    "You can carry a lot. That's bout it!":
        "Вы можете носить с собой много. Вот и всё!",
    "You do not fight. You decide who does, and they never ask why.":
        "Вы не сражаетесь. Вы решаете, кто будет сражаться, и они никогда не спрашивают почему.",
    "You are a master of ranged combat. Not close.":
        "Вы мастер дальнего боя. Вблизи — не очень.",
    "The light answers those who give it away. Heal until it overflows, then let it burn.":
        "Свет отвечает тем, кто его отдаёт. Лечите, пока он не переполнится, а потом позвольте ему сгореть.",
    "&cThe scum of the earth. Weak, fragile, and nobody sees you coming.&r":
        "&cОтбросы земли. Слабый, хрупкий — и никто не видит твоего приближения.&r",
    "Ancient scrolls are your medium; unleash powerful magic with the right knowledge.":
        "Древние свитки — ваш носитель. Раскрывайте мощную магию с правильными знаниями.",
    "You are a walking tank. Once you plant your feet, nothing on earth can move you.":
        "Ты — ходячий танк. Стоит поставить ноги на землю, и ничто на земле не сдвинет тебя с места.",
    "Creature of night, evolved into something weaker but now adapted to the sun.":
        "Существо ночи, развившееся в нечто более слабое, но теперь приспособленное к солнцу.",
    "Trained in combat, you are just stronger than the average.":
        "Обученный бою, вы просто сильнее среднего.",
}
