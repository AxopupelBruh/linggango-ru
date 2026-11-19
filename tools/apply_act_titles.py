"""Унификация названий актов: «Действие N» → «Акт N».

Трогаем ТОЛЬКО заголовки вида «Действие <римская цифра>:» (Act I:, Act II:, ...).
Все прочие вхождения слова «Действие» — обычные глаголы («Действует», «Действуйте»,
«Действительно») и остаются нетронутыми.

Что делаем:
  1) work/quests_ru.json — правим значения переводов (источник правды при пересборке);
  2) config/ftbquests/quests/**.snbt — расшифровываем LGQ1, меняем, шифруем тем же ключом;
  3) сверяем: количество квестов и id совпадают с backup/quests_original.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lgq_crypt as C  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUESTS = ROOT / "config/ftbquests/quests"
BACKUP = HERE / "backup/quests_original"
WORK = HERE / "work"

# «Действие» + необязательный ZWNJ + пробел + римская цифра + двоеточие
RE_ACT = re.compile(r"Действие(‌)?(\s+)(?=[IVX]+:)")

# структурная сигнатура: сколько квестов и какие id
RE_ID = re.compile(r'^\t\tid:\s*"([0-9A-F]+)"', re.M)
RE_Q = re.compile(r'^\ttype:\s*"minecraft:advancement"', re.M)


def sig(raw: str) -> tuple[int, list[str]]:
    return len(RE_Q.findall(raw)), RE_ID.findall(raw)


def patch_text(text: str) -> tuple[str, int]:
    return RE_ACT.subn(lambda m: "Акт" + (m.group(1) or "") + m.group(2), text)


def main() -> None:
    # --- 1) справочник переводов ---
    tr_path = WORK / "quests_ru.json"
    tr = json.loads(tr_path.read_text(encoding="utf-8"))
    changed_dict = 0
    for k, v in list(tr.items()):
        if not isinstance(v, str):
            continue
        nv, n = patch_text(v)
        if n:
            tr[k] = nv
            changed_dict += 1
    if changed_dict:
        tr_path.write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"work/quests_ru.json: обновлено значений — {changed_dict}")

    # --- 2) живые файлы квестов ---
    files_changed = 0
    hits = 0
    problems: list[str] = []
    for f in sorted(QUESTS.rglob("*.snbt")):
        rel = f.relative_to(QUESTS)
        raw = f.read_text(encoding="utf-8")
        enc = C.is_encrypted(raw)
        plain = C.decrypt(raw) if enc else raw
        new, n = patch_text(plain)
        if not n or new == plain:
            continue

        before = sig(plain)
        after = sig(new)
        if before != after:
            problems.append(f"{rel}: изменилась структура {before[0]}→{after[0]}")
            continue

        out = C.encrypt(new) if enc else new
        if enc and C.decrypt(out) != new:
            problems.append(f"{rel}: не расшифровывается после перешифровки")
            continue

        bak = BACKUP / rel
        bak.parent.mkdir(parents=True, exist_ok=True)
        if not bak.exists():
            bak.write_text(raw, encoding="utf-8")
        f.write_text(out, encoding="utf-8")
        files_changed += 1
        hits += n
        print(f"  {rel}: {n} замен")

    print(f"файлов изменено: {files_changed}, замен: {hits}")
    if problems:
        print("ПРОБЛЕМЫ:")
        for p in problems:
            print("  ", p)
        sys.exit(1)

    # --- 3) контроль: в файлах не осталось «Действие <римская>:» ---
    left = []
    for f in sorted(QUESTS.rglob("*.snbt")):
        raw = f.read_text(encoding="utf-8")
        plain = C.decrypt(raw) if C.is_encrypted(raw) else raw
        for m in RE_ACT.finditer(plain):
            left.append(f"{f.relative_to(QUESTS)}: …{plain[max(0,m.start()-30):m.end()+30]}…")
    print("остаточные «Действие N:»:", len(left))
    for x in left:
        print("  ", x)


if __name__ == "__main__":
    main()
