"""Сравнение нашего перевода квестов с чужим (k1n1maro/-Linggango).

Сопоставляем три источника по id квеста внутри одноимённых глав:
  EN   — оригинал (backup/quests_original расшифрован в plain/)
  OURS — наш текущий перевод (игра)
  THEIRS — перевод k1n1maro (открытый SNBT)

Результат: work/compare_github.json — по каждой английской строке
варианты ours/theirs + оценка, что лучше.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import ftbq_parse  # noqa: E402
import lgq_crypt as C  # noqa: E402

PLAIN = HERE / "plain/chapters"
OURS = Path("/home/ax/Documents/curseforge/minecraft/Instances/Linggango/config/ftbquests/quests/chapters")
THEIRS = Path("/tmp/lg_cmp/lg_rar/minecraft/config/ftbquests/quests/chapters")

RE_LATIN = re.compile(r"[A-Za-z]")
RE_TAG = re.compile(r"<[^<>]{0,300}>")


def sig(text: str) -> tuple:
    """Сигнатура разметки — по ней выравниваем строки внутри квеста."""
    return tuple(RE_TAG.findall(text or ""))


def align(a: list[str], b: list[str]) -> list[tuple[int, int]]:
    """Пары (индекс в a, индекс в b) по совпадению сигнатур разметки."""
    import difflib
    sm = difflib.SequenceMatcher(None, [sig(x) for x in a], [sig(x) for x in b], autojunk=False)
    pairs = []
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            pairs.append((i + k, j + k))
    return pairs


def load_ours(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    return C.decrypt(raw) if C.is_encrypted(raw) else raw


def main() -> None:
    common = sorted(p.name for p in THEIRS.glob("*.snbt") if (OURS / p.name).exists())
    rows: dict[str, dict] = {}
    stats = {"files": len(common), "quests": 0, "fields": 0, "same": 0,
             "ours_only": 0, "theirs_only": 0}
    per_file = []

    for name in common:
        en = ftbq_parse.parse_file((PLAIN / name).read_text(encoding="utf-8"))
        ours = ftbq_parse.parse_file(load_ours(OURS / name))
        theirs = ftbq_parse.parse_file((THEIRS / name).read_text(encoding="utf-8"))
        f_rows = 0
        for qid, en_texts in en.items():
            if qid not in ours:
                continue
            o = ours[qid]
            t = theirs.get(qid, [])
            pairs = align(o, t)
            for i, j in pairs:
                if i >= len(en_texts):
                    continue
                src = en_texts[i]
                if not src.strip():
                    continue
                ours_txt = o[i]
                theirs_txt = t[j]
                key = src
                prev = rows.get(key)
                if prev is None:
                    rows[key] = {"ours": ours_txt, "theirs": theirs_txt, "file": name}
                    stats["fields"] += 1
                    f_rows += 1
                    if theirs_txt is None:
                        stats["ours_only"] += 1
                    elif ours_txt == theirs_txt:
                        stats["same"] += 1
                elif prev["theirs"] is None and theirs_txt is not None:
                    prev["theirs"] = theirs_txt
            stats["quests"] += 1
        per_file.append((name, f_rows, len(en), len(ours), len(theirs)))

    out = HERE / "work/compare_github.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"глав: {stats['files']}, квестов: {stats['quests']}, уникальных строк: {stats['fields']}")
    print(f"совпали: {stats['same']}, только у нас: {stats['ours_only']}")
    print(f"сохранено: {out}")

    # сводка по файлам
    print("\nфайл               наших  их  совпали")
    for name, f_rows, ne, no, nt in per_file:
        same = sum(1 for r in rows.values() if r["file"] == name and r["theirs"] == r["ours"])
        print(f"{name:24s} {f_rows:5d} {nt:4d} {same:6d}")


if __name__ == "__main__":
    main()
