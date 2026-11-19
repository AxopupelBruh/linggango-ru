"""Пути: где инстанс сборки, где рабочие данные, где бэкапы.

Рабочий каталог перевода лежит **вне** инстанса сборки, поэтому скрипты
не могут искать инстанс в родительской папке. Путь задаётся тремя способами
(в порядке приоритета):

  1) переменная окружения ``LINGGANGO_INSTANCE``;
  2) файл ``instance.path`` рядом со скриптами (одна строка с путём);
  3) значение по умолчанию :data:`DEFAULT_INSTANCE`.

Проверить, куда смотрит скрипт:

    python3 paths.py
"""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULT_INSTANCE = "/home/ax/Documents/curseforge/minecraft/Instances/Linggango"


def _instance() -> Path:
    env = os.environ.get("LINGGANGO_INSTANCE")
    if env:
        return Path(env).expanduser().resolve()
    cfg = HERE / "instance.path"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8").strip()
        if text:
            return Path(text).expanduser().resolve()
    return Path(DEFAULT_INSTANCE).expanduser().resolve()


#: корень инстанса сборки (mods/, resourcepacks/, config/, kubejs/)
INSTANCE = _instance()

#: рабочие данные перевода (словари, кэши, отчёты)
WORK = HERE / "work"
WORK_DIR = WORK

#: бэкапы оригиналов (jar-ы, квесты)
BACKUP = HERE / "backup"

#: папка сборки релиза
RELEASE = HERE / "release"

if __name__ == "__main__":
    print(f"рабочий каталог : {HERE}")
    print(f"инстанс сборки  : {INSTANCE}")
    print(f"  существует?    : {'да' if INSTANCE.exists() else 'НЕТ'}")
    print(f"  mods/          : {'да' if (INSTANCE / 'mods').exists() else 'НЕТ'}")
    print(f"рабочие данные  : {WORK}")
    print(f"бэкапы          : {BACKUP}")
