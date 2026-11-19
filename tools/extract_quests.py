"""Сбор всех английских строк из расшифрованных файлов FTB Quests сборки Linggango."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lgq_crypt as C  # noqa: E402

QUESTS = Path(__file__).resolve().parents[1] / "config/ftbquests/quests"

# Поля FTB Quests, в которых лежит видимый текст
TEXT_FIELDS = ("title", "subtitle", "description")


def collect():
    entries = []  # (file, field, text)
    files = sorted(QUESTS.rglob("*.snbt"))
    ok = fail = 0
    for f in files:
        raw = f.read_text(encoding="utf-8")
        if C.is_encrypted(raw):
            try:
                raw = C.decrypt(raw)
            except Exception as exc:
                print(f"!! {f.relative_to(QUESTS)}: {exc}", file=sys.stderr)
                fail += 1
                continue
            ok += 1
        for field in TEXT_FIELDS:
            for m in re.finditer(rf'^\s*{field}:\s*"((?:[^"\\]|\\.)*)"\s*$', raw, re.M):
                entries.append((f.relative_to(QUESTS).as_posix(), field, m.group(1)))
        # hover: [ "..." ... ]
        for m in re.finditer(r'hover:\s*\[(.*?)\]', raw, re.S):
            for s in re.finditer(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
                entries.append((f.relative_to(QUESTS).as_posix(), "hover", s.group(1)))
    return entries, ok, fail, len(files)


if __name__ == "__main__":
    entries, ok, fail, total = collect()
    print(f"файлов: {total}, расшифровано: {ok}, с ошибкой: {fail}")
    print(f"строк всего: {len(entries)}")
    from collections import Counter
    print("по полям:", Counter(f for _, f, _ in entries).most_common())
    uniq = {}
    for f, fld, t in entries:
        uniq.setdefault(t, []).append((f, fld))
    print(f"уникальных строк: {len(uniq)}")
    words = sum(len(t.split()) for t in uniq)
    print(f"слов (en): ~{words}")
    out = Path(__file__).parent / "quest_strings.json"
    out.write_text(json.dumps(
        [{"text": t, "where": [{"file": f, "field": fl} for f, fl in v]} for t, v in uniq.items()],
        ensure_ascii=False, indent=1))
    print("saved:", out)
