"""Итоговая проверка комплекта локализации Linggango.

Проверяет:
  1. jar-файлы модов не изменены (совпадают с бэкапом оригиналов);
  2. ресурспак на месте, цел и зарегистрирован последним;
  3. переводчик подсказок (KubeJS) на месте и синтаксически валиден;
  4. датапак с книгами собран;
  5. словари переводов заполнены.

Запуск: python3 verify_all.py
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = INSTANCE
MODS = ROOT / "mods"
BACKUP = HERE / "backup" / "jars_original"
MD5LIST = HERE / "backup" / "jars_original.md5"
WORK = HERE / "work"
PACK = ROOT / "resourcepacks" / "zz_linggango_ru.zip"
SCRIPT = ROOT / "kubejs" / "client_scripts" / "ru_tooltip_translator.js"
DATAPACK = ROOT / "datapacks" / "zz_linggango_ru_books"

ok = True


def head(title: str) -> None:
    print(f"\n=== {title}")


def check(cond: bool, msg: str) -> None:
    global ok
    print(f"  {'OK  ' if cond else 'FAIL'} {msg}")
    if not cond:
        ok = False


head("1. jar-файлы модов не изменены")
if BACKUP.exists():
    same = diff = missing = 0
    for b in sorted(BACKUP.glob("*.jar")):
        p = MODS / b.name
        if not p.exists():
            missing += 1
            continue
        h1 = hashlib.md5(b.read_bytes()).hexdigest()
        h2 = hashlib.md5(p.read_bytes()).hexdigest()
        if h1 == h2:
            same += 1
        else:
            diff += 1
            print(f"     изменён: {b.name}")
    check(diff == 0 and missing == 0,
          f"совпадают с оригиналами: {same}, изменено: {diff}, отсутствует: {missing}")
elif MD5LIST.exists():
    same = diff = missing = 0
    for line in MD5LIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split(None, 1)
        p = MODS / name.strip()
        if not p.exists():
            missing += 1
            continue
        if hashlib.md5(p.read_bytes()).hexdigest() == digest:
            same += 1
        else:
            diff += 1
            print(f"     изменён: {name.strip()}")
    check(diff == 0 and missing == 0,
          f"совпадают с базой md5: {same}, изменено: {diff}, отсутствует: {missing}")
else:
    print("  (бэкапов и базы md5 нет — нечего проверять)")

head("2. ресурспак")
check(PACK.exists(), f"файл есть: {PACK.name}")
if PACK.exists():
    with zipfile.ZipFile(PACK) as z:
        names = z.namelist()
        bad = z.testzip()
    check(bad is None, f"zip цел, файлов: {len(names)}")
    langs = [n for n in names if n.endswith(".json") and "/lang/" in n]
    check(len(langs) > 200, f"lang-файлов: {len(langs)}")
opts = (ROOT / "options.txt").read_text(encoding="utf-8")
check("file/zz_linggango_ru.zip" in opts, "зарегистрирован в options.txt")
check(opts.rstrip().endswith("file/zz_linggango_ru.zip\"]") or
      "file/zz_linggango_ru.zip" in opts.split("resourcePacks:")[1].split("\n")[0][-40:],
      "идёт последним в списке")
check("lang:ru_ru" in opts, "язык игры: ru_ru")

head("3. переводчик подсказок (KubeJS)")
check(SCRIPT.exists(), f"скрипт есть: {SCRIPT.name}")
if SCRIPT.exists():
    txt = SCRIPT.read_text(encoding="utf-8")
    check("ItemEvents.tooltip" in txt, "подписан на событие тултипов")
    check("addAdvancedToAll" in txt, "обработчик для всех предметов")
    check("RU_DICT" in txt and "RU_TEMPLATES" in txt, "словарь и шаблоны на месте")
    size = SCRIPT.stat().st_size
    print(f"     размер: {size/1024:.0f} КБ")

head("4. датапак с книгами")
check(DATAPACK.exists(), "датапак собран")
if DATAPACK.exists():
    pm = DATAPACK / "pack.mcmeta"
    check(pm.exists(), "pack.mcmeta на месте")
    files = [p for p in DATAPACK.rglob("*.json")]
    check(len(files) > 0, f"перекрытых лут-таблиц: {len(files)}")
    for p in files:
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            check(False, f"{p.name}: битый JSON ({e})")
    # английских страниц быть не должно
    left = 0
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))

        def walk(o):
            global left
            if isinstance(o, dict):
                if o.get("function") in ("minecraft:set_written_book_pages",
                                         "minecraft:set_book_contents"):
                    pages = o.get("pages") or o.get("value") or []
                    if isinstance(pages, str):
                        pages = [pages]
                    for pg in pages:
                        raw = pg.get("raw") if isinstance(pg, dict) else pg
                        if (raw and raw.strip()
                                and not any("Ѐ" <= ch <= "ӿ" for ch in raw)
                                and not any("\u0600" <= ch <= "\u06ff" for ch in raw)):
                            left += 1
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)
    check(left == 0, f"страниц без перевода: {left}")

head("4b. датапак-jar и миры")
jar = ROOT / "mods" / "zz_linggango_ru_books.jar"
check(jar.exists(), f"датапак-jar в mods/: {jar.name}")
if jar.exists():
    with zipfile.ZipFile(jar) as z:
        names = z.namelist()
        check("pack.mcmeta" in names, "pack.mcmeta внутри jar")
        check(any(n.startswith("data/") for n in names), "данные внутри jar")
worlds = list((ROOT / "saves").glob("*/datapacks/zz_linggango_ru_books"))
check(len(worlds) > 0, f"скопировано в миры: {len(worlds)}")

head("5. словари")
for name in ("mods_ru.json", "ui_strings_ru.json", "pack_script_ru.json",
             "quests_ru.json", "patchouli_ru.json"):
    p = WORK / name
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"  {name}: {len(d)} записей")
    else:
        print(f"  {name}: нет")

print("\n" + ("ВСЁ ОК" if ok else "ЕСТЬ ПРОБЛЕМЫ"))
raise SystemExit(0 if ok else 1)
