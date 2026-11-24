"""Сборка архива установки перевода для релиза на GitHub.

Архив распаковывается прямо в папку инстанса сборки:

    linggango-ru-v6.6.6.zip
    └── linggango-ru/
        ├── УСТАНОВКА.md
        ├── install.sh
        └── install/
            ├── resourcepacks/zz_linggango_ru.zip
            ├── kubejs/…
            ├── mods/zz_linggango_ru_books.jar
            ├── datapacks/zz_linggango_ru_books/
            └── config/ftbquests/quests/

Запуск:

    python3 build_release_archive.py                # → release/linggango-ru-v6.6.6.zip
    python3 build_release_archive.py --version 6.6.6 --build V6.6.6cf
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
INSTALL = REPO / "install"
OUT_DIR = REPO / "release"

DEFAULT_VERSION = "6.6.6"
DEFAULT_BUILD = "V6.6.6cf"

INSTALL_SH = """#!/usr/bin/env bash
# Установка русского перевода Linggango в папку инстанса сборки.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  echo "Укажи путь к папке сборки (та, где лежат mods, config, resourcepacks):"
  echo "  ./install.sh '/путь/к/папке/сборки'"
  exit 1
fi

if [ ! -d "$TARGET/mods" ]; then
  echo "ОШИБКА: в '$TARGET' нет папки mods. Это не папка сборки." >&2
  exit 1
fi

echo "Ставим перевод в: $TARGET"

# квесты: сохраняем текущие, если есть — пригодится, если сборка обновится
if [ -d "$TARGET/config/ftbquests/quests" ]; then
  BACKUP="$TARGET/config/ftbquests/quests.backup.$(date +%Y%m%d_%H%M%S)"
  cp -r "$TARGET/config/ftbquests/quests" "$BACKUP"
  echo "  старые квесты сохранены: $(basename "$BACKUP")"
fi

cp -r "$HERE/install/." "$TARGET/"

echo
echo "Готово. Осталось проверить:"
echo "  1. в options.txt стоит  lang:ru_ru"
echo "  2. в списке ресурспаков наш zz_linggango_ru.zip ПОСЛЕДНИЙ"
echo "  3. в игре: Options -> Language -> Русский"
"""


def build(version: str, build_name: str) -> Path:
    if not INSTALL.is_dir():
        raise SystemExit(f"нет папки {INSTALL}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stage = OUT_DIR / "_stage" / f"linggango-ru-{version}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    shutil.copytree(INSTALL, stage / "install")
    (stage / "install.sh").write_text(INSTALL_SH, encoding="utf-8")
    (stage / "install.sh").chmod(0o755)

    readme = REPO / "docs" / "УСТАНОВКА.md"
    if readme.exists():
        shutil.copy2(readme, stage / "УСТАНОВКА.md")
    else:
        (stage / "УСТАНОВКА.md").write_text(
            "# Установка\n\nСкопируй папку install/ в корень инстанса сборки.\n",
            encoding="utf-8")

    archive = OUT_DIR / f"linggango-ru-v{version}.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, Path("linggango-ru") / f.relative_to(stage))
    shutil.rmtree(stage.parent, ignore_errors=True)
    return archive


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--build", default=DEFAULT_BUILD)
    args = ap.parse_args()
    archive = build(args.version, args.build)
    print(f"архив: {archive} ({archive.stat().st_size // 1024} КБ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
