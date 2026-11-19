"""Сборка датапака с книгами в единый вид: папка + jar в mods/ + копии в мирах.

Запуск после `python3 fix_books.py build`:
    python3 sync_books_datapack.py
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATAPACK = ROOT / "datapacks" / "zz_linggango_ru_books"
JAR = ROOT / "mods" / "zz_linggango_ru_books.jar"
SAVES = ROOT / "saves"


def build_jar() -> int:
    if JAR.exists():
        JAR.unlink()
    with zipfile.ZipFile(JAR, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(DATAPACK.rglob("*")):
            if f.is_file():
                z.write(f, str(f.relative_to(DATAPACK)))
    return len(zipfile.ZipFile(JAR).namelist())


def copy_to_worlds() -> int:
    n = 0
    for world in SAVES.glob("*"):
        if not world.is_dir():
            continue
        dst = world / "datapacks" / "zz_linggango_ru_books"
        if not (world / "datapacks").exists():
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(DATAPACK, dst)
        n += 1
    return n


def main() -> None:
    if not DATAPACK.exists():
        raise SystemExit("нет папки датапака — сначала python3 fix_books.py build")
    files = build_jar()
    worlds = copy_to_worlds()
    print(f"jar: {JAR} ({files} файлов)")
    print(f"скопировано в миры: {worlds}")


if __name__ == "__main__":
    main()
