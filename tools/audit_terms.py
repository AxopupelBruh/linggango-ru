"""Аудит терминологии: ищем один английский термин, переведённый у нас разными словами.

Источники: work/quests_ru.json, work/mods_ru.json, work/kubejs_ru.json.
Эталон терминов: term_map_quests_google.json (ru/deepl — предложенные варианты).

Алгоритм:
  1. по n-граммам английского текста находим термин из карты;
  2. смотрим, какие из предложенных русских вариантов реально встречаются
     в переводе этой же строки;
  3. если в термине встречаются 2+ разных варианта (каждый ≥ MIN_COUNT раз),
     термин считается несогласованным.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
MIN_COUNT = 3
MAX_NGRAM = 6

RE_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def load_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for name in ("quests_ru", "mods_ru", "kubejs_ru", "patchouli_ru"):
        p = WORK / f"{name}.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for en, ru in data.items():
            if isinstance(ru, str) and ru:
                pairs.append((en, ru))
    return pairs


def main() -> None:
    tm = json.loads((HERE / "term_map_quests_google.json").read_text(encoding="utf-8"))
    # термин -> список кандидатов
    term_variants: dict[str, set[str]] = defaultdict(set)
    for term, info in tm.items():
        variants = {info["ru"], info.get("deepl") or info["ru"]}
        variants = {v.strip() for v in variants if v and v.strip()}
        if len(variants) > 1:
            term_variants[term.lower()] = variants

    pairs = load_pairs()
    print(f"пар строк: {len(pairs):,}, терминов с вариантами: {len(term_variants)}")

    used: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    other: dict[str, int] = defaultdict(int)
    term_index = {t: t for t in term_variants}

    for en, ru in pairs:
        ru_low = ru.lower()
        words = [w.lower() for w in RE_WORD.findall(en)]
        seen_terms = set()
        for i in range(len(words)):
            for n in range(1, MAX_NGRAM + 1):
                if i + n > len(words):
                    break
                phrase = " ".join(words[i:i + n])
                if phrase not in term_index or phrase in seen_terms:
                    continue
                seen_terms.add(phrase)
                variants = term_variants[phrase]
                hit = False
                for v in variants:
                    if v.lower() in ru_low:
                        used[phrase][v] += 1
                        hit = True
                if not hit:
                    other[phrase] += 1

    bad = []
    for term, counts in used.items():
        if len(counts) < 2:
            continue
        top = sorted(counts.items(), key=lambda x: -x[1])
        if top[0][1] >= MIN_COUNT and top[1][1] >= MIN_COUNT:
            bad.append((top[0][1], term, top, other.get(term, 0)))
    bad.sort(reverse=True)

    print(f"\nнесогласованных терминов: {len(bad)}\n")
    for cnt, term, top, oth in bad:
        variants = ", ".join(f"{v!r}×{c}" for v, c in top)
        print(f"  {term!r}: {variants}" + (f"  (ещё вариантов: {oth})" if oth else ""))

    out = WORK / "audit_terms.json"
    out.write_text(json.dumps(
        [{"term": t, "variants": dict(c), "other": oth} for _, t, c, oth in bad],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nсохранено: {out}")


if __name__ == "__main__":
    main()
