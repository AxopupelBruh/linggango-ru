"""Одноразовая миграция: перевести скрипты с «инстанс = родительская папка»
на настраиваемый путь из paths.py.

Рабочий каталог перевода переезжает из инстанса сборки наружу, поэтому
`HERE.parent` больше не указывает на инстанс. Заменяем такие обращения на
`INSTANCE` из paths.py.

Запуск (из рабочего каталога):
    python3 migrate_paths.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# точные замены строк
REPL = [
    ("ROOT = HERE.parent", "ROOT = INSTANCE"),
    ("ROOT = Path(__file__).resolve().parents[1]", "ROOT = INSTANCE"),
    ("ROOT = Path(__file__).resolve().parent.parent", "ROOT = INSTANCE"),
    ('ROOT = Path("/home/ax/Documents/curseforge/minecraft/Instances/Linggango")',
     "ROOT = INSTANCE"),
    ('MODS = HERE.parent / "mods"', 'MODS = INSTANCE / "mods"'),
    ('KUBE = HERE.parent / "kubejs"', 'KUBE = INSTANCE / "kubejs"'),
    ('KUBE = HERE.parent / "kubejs" / "client_scripts"',
     'KUBE = INSTANCE / "kubejs" / "client_scripts"'),
    ('WORK = ROOT / ".linggango-translate" / "work"', "WORK = WORK_DIR"),
    ('WORK = HERE.parent / ".linggango-translate" / "work"', "WORK = WORK_DIR"),
    ('sys.path.insert(0, str(ROOT / ".linggango-translate"))',
     "sys.path.insert(0, str(HERE))"),
    ('sys.path.insert(0, str(HERE.parent / ".linggango-translate"))',
     "sys.path.insert(0, str(HERE))"),
]

IMPORT_LINE = "from paths import INSTANCE, WORK_DIR  # noqa: E402"

# куда вставлять импорт: после sys.path.insert, иначе после «from pathlib import Path»
ANCHORS = [
    "sys.path.insert(0, str(Path(__file__).parent))",
    "sys.path.insert(0, str(Path(__file__).resolve().parent))",
    "from pathlib import Path",
]


def migrate(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    out = src
    for old, new in REPL:
        out = out.replace(old, new)

    # нужен ли импорт paths
    needs = ("INSTANCE" in out and "from paths import" not in out) or \
            ("WORK_DIR" in out and "from paths import" not in out)
    if needs and "paths import" not in out:
        for anchor in ANCHORS:
            idx = out.find(anchor)
            if idx != -1:
                end = out.index("\n", idx) + 1
                out = out[:end] + IMPORT_LINE + "\n" + out[end:]
                break

    if out == src:
        return False
    try:
        ast.parse(out)
    except SyntaxError as e:
        print(f"  СИНТАКСИС не сохранён, пропускаю {path.name}: {e}")
        return False
    path.write_text(out, encoding="utf-8")
    return True


def main() -> None:
    changed = []
    for p in sorted(HERE.glob("*.py")):
        if p.name in ("migrate_paths.py", "paths.py"):
            continue
        if migrate(p):
            changed.append(p.name)
    print(f"обновлено файлов: {len(changed)}")
    for n in changed:
        print("  ", n)

    # контроль: не осталось ли обращений к инстансу через HERE.parent
    left = []
    for p in sorted(HERE.glob("*.py")):
        text = p.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "HERE.parent" in line or "parent.parent" in line or "parents[1]" in line:
                left.append(f"{p.name}:{i}: {line.strip()}")
    if left:
        print("\nОСТАЛИСЬ обращения через родительскую папку:")
        for x in left:
            print("  ", x)
        sys.exit(1)
    print("\nвсе обращения к инстансу переведены на INSTANCE")


if __name__ == "__main__":
    main()
