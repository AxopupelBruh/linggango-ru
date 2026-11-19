"""Поиск английских строк, зашитых в Java-код модов (не в lang-файлы).

Многие моды формируют тултипы литералами прямо в коде:
    Component.literal("§6Passive Effect:")
Ресурспак такие строки не перекрывает — нужен патч jar.

Отбор: строка содержит §-код (признак игрового текста), состоит из
ASCII-слов, не похожа на идентификатор/путь/форматную строку.

Результат: work/java_strings.json = {строка: ["jar|class", ...]}
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODS = ROOT / "mods"
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from classfile import ClassFile  # noqa: E402

WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CODE = re.compile(r"§[0-9a-fk-orA-FK-OR]")


def candidate(s: str) -> bool:
    """Похоже ли на пользовательский английский текст с §-кодами."""
    if not s or len(s) > 300:
        return False
    body = CODE.sub("", s)
    if not body.isascii():
        return False
    if CTRL.search(s) or "§" not in s:
        return False
    if re.search(r"[/\\{}\[\]<>]", s):
        return False
    if not WORD.findall(body):
        return False
    if re.search(r"[a-z]{2,}[._][a-z]{2,}", body):
        return False
    if re.search(r"%[a-zA-Z]", body):
        return False
    return True


def main() -> int:
    # сканируем ОРИГИНАЛЬНЫЕ jar-файлы (бэкап), если они есть: иначе повторный
    # запуск не найдёт уже переведённые строки
    backup = HERE / "backup" / "jars_original"
    source = backup if backup.exists() else MODS
    found: dict[str, list[str]] = {}
    classes = 0
    for jar in sorted(source.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if not name.endswith(".class"):
                continue
            try:
                cf = ClassFile(z.read(name))
            except Exception:
                continue
            classes += 1
            for s in cf.utf8_strings():
                if candidate(s):
                    found.setdefault(s, []).append(f"{jar.name}|{name}")

    out = {s: sorted(set(locs)) for s, locs in sorted(found.items())}
    (WORK / "java_strings.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    per_mod: dict[str, int] = {}
    for locs in out.values():
        for loc in locs:
            jar = loc.split("|")[0]
            per_mod[jar] = per_mod.get(jar, 0) + 1
    print(f"классов просмотрено: {classes}")
    print(f"уникальных строк: {len(out)}, модов затронуто: {len(per_mod)}")
    print("\nпо модам:")
    for jar, cnt in sorted(per_mod.items(), key=lambda kv: -kv[1]):
        print(f"  {cnt:5d}  {jar[:56]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
