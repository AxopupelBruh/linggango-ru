#!/usr/bin/env python3
"""Возврат английского синтаксиса в справке ETF/EMF/Lootr/Quark и подкоманды /animus."""
import json, re, shutil
from pathlib import Path

W = Path(__file__).resolve().parent
MODS = W / 'work' / 'mods_ru.json'
PATCH = W / 'work' / 'patchouli_ru.json'

shutil.copy2(MODS, '/tmp/opencode/mods_ru.before_syntax.json')
shutil.copy2(PATCH, '/tmp/opencode/patchouli_ru.before_syntax.json')

mods = json.loads(MODS.read_text(encoding='utf-8'))
patch = json.loads(PATCH.read_text(encoding='utf-8'))

syntax_fixed = 0
for k, v in list(mods.items()):
    en_lines = [l for l in k.split('\n') if l.startswith('§a') and '=' in l]
    if not en_lines:
        continue
    ru_lines = v.split('\n')
    # индексы §a-строк с '=' в переводе
    idx = [i for i, l in enumerate(ru_lines) if l.startswith('§a') and '=' in l]
    if len(idx) != len(en_lines):
        print('!! не совпало число строк:', repr(k)[:80])
        continue
    if [ru_lines[i] for i in idx] == en_lines:
        continue
    for i, en in zip(idx, en_lines):
        ru_lines[i] = en
    mods[k] = '\n'.join(ru_lines)
    syntax_fixed += 1

print('строк синтаксиса восстановлено:', syntax_fixed)

# точечные правки: литеральные форматы, примеры, команды
manual = {
    # формат переменных CEM
    'Entity variables are specified in the format "var.<name>" (float) or "varb.<name>" (boolean) \n\nThe name can be any string, for example "var.xyz", "var.last_rx", etc.\n\nThe variable is attached to the rendered entity and has a default value 0 or false.\n\nEntity variables are useful for storing animation data between frames.':
        [('var.<имя>', 'var.<name>'), ('varb.<имя>', 'varb.<name>')],
    'Global variables are specified in the format "global_var.<name>" (float) or "global_varb.<name>" (boolean) \nThe name can be any string, for example "global_var.xyz", "global_var.last_rx", etc.\nThe variable is globally saved and has a default value 0 or false.\nGlobal variables are useful for storing animation data used by multiple entities.':
        [('global_var.<имя>', 'global_var.<name>'), ('global_varb.<имя>', 'global_varb.<name>')],
    'The format is quark.config.[(category).]+.(name).<name|desc>':
        [('<название|описание>', '<name|desc>')],
    'Text Animator tags to skip. \'<glitch >\' matches any tag starting with it.':
        [("'<glitch>'", "'<glitch >'")],
    # примеры значений в справке
    'Block Above \nVary based on the first non-air block above the entity, no matter the distance\nExample: blockAbove.1=oak_leaves\n§ablockAbove.<n>=<list>':
        [('blockAbove.1=дубовые листья', 'blockAbove.1=oak_leaves')],
    'Block Above Solid \nVary based on the first solid non-air block above the entity, no matter the distance, only triggers for the first solid block found.\nExample: blockAboveSolid.1=stone\n§ablockAboveSolid.<n>=<list>':
        [('blockAboveSolid.1=камень', 'blockAboveSolid.1=stone')],
    'Block Below \nVary based on the first non-air block below the entity, no matter the distance\nExample: blockBelow.1=oak_leaves\n§ablockBelow.<n>=<list>':
        [('blockBelow.1=дубовые листья', 'blockBelow.1=oak_leaves')],
    'Block Below Solid \nVary based on the first solid non-air block below the entity, no matter the distance, only triggers for the first solid block found.\nExample: blockBelowSolid.1=oak_leaves\n§ablockBelowSolid.<n>=<list>':
        [('blockBelowSolid.1=дубовые листья', 'blockBelowSolid.1=oak_leaves')],
    'Temperature \nSelect what temperature it must be at the entities spawn location, this is internally driven by Biome settings as well as world height, for example if the biome has precipitation it will snow if the position is below 0.15 temperature\nExample: temperature.1=0.2-0.15\n§atemperature.<n>=<list>':
        [('Пример: температура.1=0,2-0,15.', 'Пример: temperature.1=0.2-0.15.')],
    'Minecraft Version \nSelect which minecraft version it must be\nExample: minecraftVersion.1=1.18.2 1.17 1.20-1.99\n§aminecraftVersion.<n>=<list>':
        [('minecraftVersion.1=1.18.2 1,17 1,20-1,99', 'minecraftVersion.1=1.18.2 1.17 1.20-1.99')],
    'Height ranges\nReplaces legacy minHeight and maxHeight properties.\nSince 1.18 negative values may be specified for height. When used in a range they can be put in brackets for Optifine but will function as written for ETF.\nETF supports:             1 2-4   -65-2  -65--2   1-4   (-65)-2  (-65)-(-2)\nOptifine supports only:   1 2-4                   1-4   (-65)-2  (-65)-(-2)\n§aheights.<n>=<height_ranges>\n\nHeight legacy\nETF also supports the legacy minHeight and maxHeight properties.\nthey can be a single number from -64 to 319\n§aminHeight.<n>=<height>\n§amaxHeight.<n>=<height>':
        [('ETF поддерживает: 1 2-4   -65-2  -65--2   1-4   (-65)-2  (-65)-(-2)',
          'ETF поддерживает:             1 2-4   -65-2  -65--2   1-4   (-65)-2  (-65)-(-2)'),
         ('Optifine поддерживает только:   1 2-4 1-4   (-65)-2  (-65)-(-2)',
          'Optifine поддерживает только:   1 2-4                   1-4   (-65)-2  (-65)-(-2)')],
    'List of game modes of the client player\nIn vanilla these are: 0=survival, 1=creative, 2=adventure, 3=spectator\n§aclientGameMode.<n>=<list>':
        [('0=выживание, 1=творчество, 2=приключение, 3=наблюдатель.',
          '0=survival, 1=creative, 2=adventure, 3=spectator')],
    'List of difficulties\nVanilla difficulties are: 0=peaceful, 1=easy, 2=normal, 3=hard\n§adifficulty.<n>=<list>':
        [('0 = мирная, 1 = лёгкая, 2 = нормальная, 3 = сложная.',
          '0=peaceful, 1=easy, 2=normal, 3=hard')],
    # синтаксис команды /lootr — аргументы вводятся как есть
    '/lootr barrel | barrel <loot-table> | chest | chest <loot-table> | cart | cart <loot-table> | shulker | shulker <loot-table> | convert | custom <id> | refresh | decay':
        [(mods['/lootr barrel | barrel <loot-table> | chest | chest <loot-table> | cart | cart <loot-table> | shulker | shulker <loot-table> | convert | custom <id> | refresh | decay'],
          '/lootr barrel | barrel <loot-table> | chest | chest <loot-table> | cart | cart <loot-table> | shulker | shulker <loot-table> | convert | custom <id> | refresh | decay')],
}

applied = 0
for key, subs in manual.items():
    if key not in mods:
        print('!! ключ не найден:', repr(key)[:80])
        continue
    val = mods[key]
    for old, new in subs:
        if old not in val:
            print('!! не найдено в переводе:', repr(old)[:70])
            continue
        val = val.replace(old, new)
        applied += 1
    mods[key] = val

print('точечных правок:', applied)

# /animus <подкоманда> -> <subcommand>
n = 0
for k, v in list(patch.items()):
    if '<подкоманда>' in v:
        patch[k] = v.replace('<подкоманда>', '<subcommand>')
        n += 1
print('patchouli правок:', n)

MODS.write_text(json.dumps(mods, ensure_ascii=False, indent=1), encoding='utf-8')
PATCH.write_text(json.dumps(patch, ensure_ascii=False, indent=1), encoding='utf-8')
print('записано')
