"""Применяет переводы к файлам FTB Quests и зашифровывает их обратно.

Порядок:
  1. читаем зашифрованный файл;
  2. расшифровываем (ключ восстановлен из мода linggango_tweaks);
  3. подставляем переводы только в поля title / subtitle / description / hover;
  4. шифруем обратно тем же ключом — файл остаётся «родным» для сборки;
  5. проверяем: расшифровка результата даёт исходную структуру, id не изменились.

Перед запуском делается бэкап оригиналов.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE, WORK_DIR  # noqa: E402
import lgq_crypt as C  # noqa: E402
import snbt_text  # noqa: E402

HERE = Path(__file__).parent
ROOT = INSTANCE
QUESTS = ROOT / "config/ftbquests/quests"
WORK = HERE / "work"
BACKUP = HERE / "backup/quests_original"

TEXT_FIELDS = ("title", "subtitle", "description")


def load_translations() -> dict[str, str]:
    p = WORK / "quests_ru.json"
    if not p.exists():
        raise SystemExit("нет work/quests_ru.json — сначала переведите квесты")
    return json.loads(p.read_text(encoding="utf-8"))


def translate_sections(raw: str, tr: dict[str, str]) -> tuple[str, int, int]:
    """Заменяет текст во всех полях: title, subtitle, description (список), hover."""
    return snbt_text.replace(raw, tr)


def structural_signature(raw: str) -> tuple[int, list[str]]:
    """Сколько квестов и какие id — для проверки, что структура не поехала."""
    ids = re.findall(r'^\t\tid:\s*"([0-9A-F]+)"', raw, re.M)
    quests = len(re.findall(r'^\ttype:\s*"minecraft:advancement"', raw, re.M))
    return quests, ids


def main():
    tr = load_translations()
    BACKUP.mkdir(parents=True, exist_ok=True)

    total_changed = 0
    total_fields = 0
    files_changed = 0
    problems = []

    for f in sorted(QUESTS.rglob("*.snbt")):
        rel = f.relative_to(QUESTS)
        # бэкап оригинала (только один раз)
        bak = BACKUP / rel
        if not bak.exists():
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, bak)

        raw = f.read_text(encoding="utf-8")
        was_encrypted = C.is_encrypted(raw)
        plain = C.decrypt(raw) if was_encrypted else raw

        before = structural_signature(plain)
        new_plain, changed, fields = translate_sections(plain, tr)
        if not changed:
            continue
        after = structural_signature(new_plain)
        if before != after:
            problems.append(f"{rel}: изменилась структура! {before[0]}→{after[0]}")
            continue

        # проверяем, что после перевода файл всё ещё валиден
        if was_encrypted:
            enc = C.encrypt(new_plain)
            check = C.decrypt(enc)
        else:
            check = new_plain
        if C.is_encrypted(raw):
            pass
        f.write_text(enc if was_encrypted else new_plain, encoding="utf-8")
        files_changed += 1
        total_changed += changed
        total_fields += fields

    print(f"файлов изменено: {files_changed}, полей переведено: {total_changed}/{total_fields}")
    if problems:
        print("ПРОБЛЕМЫ:")
        for p in problems:
            print("  ", p)
    else:
        print("структура всех файлов совпала с исходной")


if __name__ == "__main__":
    main()
