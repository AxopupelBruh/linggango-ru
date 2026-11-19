"""Переприменяет весь перевод после обновления сборки (одна команда).

Зачем: пак Linggango при обновлении перезаписывает config/ и kubejs/ — вместе
с нашими переводами. После установки новой версии нужно вернуть русский.

Порядок (каждый шаг зависит от предыдущего):

  1. apply_quests.py          — квесты FTB (расшифровка → перевод → шифрование)
  2. apply_extra.py           — конфиги: классы, подсказки, сложности, механизмы
  3. apply_machinery_lang.py  — названия блоков механизмов (lang-файл в config)
  4. apply_kubejs.py          — kubejs: ru_ru в assets + блок переименований в lang.js
  5. build_resourcepack.py    — ресурспак + регистрация пака последним
  6. build_tooltip_script.py  — скрипт перевода тултипов
  7. fix_books.py build       — датапак с книгами
  8. sync_books_datapack.py   — jar датапака + копии в миры
  9. verify_all.py            — приёмка

Запуск:
    python3 reapply_translation.py
    python3 reapply_translation.py --skip 5,6   # пропустить шаги
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

STEPS = [
    ("1", "квесты FTB", [sys.executable, "apply_quests.py"]),
    ("2", "конфиги сборки", [sys.executable, "apply_extra.py"]),
    ("3", "названия блоков механизмов", [sys.executable, "apply_machinery_lang.py"]),
    ("4", "kubejs (ru_ru + lang.js)", [sys.executable, "apply_kubejs.py"]),
    ("5", "ресурспак", [sys.executable, "build_resourcepack.py"]),
    ("6", "скрипт тултипов", [sys.executable, "build_tooltip_script.py"]),
    ("7", "датапак книг (сборка)", [sys.executable, "fix_books.py", "build"]),
    ("8", "датапак книг (jar и миры)", [sys.executable, "sync_books_datapack.py"]),
    ("9", "приёмка", [sys.executable, "verify_all.py"]),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="переприменение перевода после обновления")
    ap.add_argument("--skip", default="", help="номера шагов через запятую")
    args = ap.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    failed = []
    for num, title, cmd in STEPS:
        if num in skip:
            print(f"\n=== шаг {num}: {title} — ПРОПУЩЕН")
            continue
        print(f"\n=== шаг {num}: {title}")
        print(f"    $ {' '.join(cmd)}", flush=True)
        rc = subprocess.run(cmd, cwd=HERE).returncode
        if rc != 0:
            print(f"    !! шаг {num} упал (код {rc})")
            failed.append(num)
            break
    if failed:
        print(f"\nостановились на шаге {failed[0]}")
        return 1
    print("\nвсе шаги выполнены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
