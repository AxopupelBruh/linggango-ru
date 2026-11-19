"""Перепереводит строки, где перевод остался битым.

Причины:
  * в переводе остались артефакты плейсхолдеров («найдете[[13]] костные блоки»);
  * разметка квестов ([gap=N], [!danger], {image:…}) не совпала по числу токенов
    и восстановить её позиционно не вышло.

Строки переводятся заново исправленным протектором (разметка защищена),
результат принимается только если он лучше прежнего.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
sys.path.insert(0, str(HERE))
from fixup import TermFixer, load_term_map  # noqa: E402
from tr_engine import (GoogleBackend, Translator, load_glossary,  # noqa: E402
                       quality, RE_MARKUP)

BROKEN = re.compile(r"\[\[\d+\]\]|\[\d+\]")


def main() -> None:
    path = WORK / "quests_ru.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    broken = [k for k, v in data.items() if isinstance(v, str) and BROKEN.search(v)]
    # строки, где число «скобочных» токенов в переводе не совпало с оригиналом
    TOKEN = re.compile(r"\{image:[^}]*\}|\[[^\[\]]{0,160}\]")
    mismatch = [k for k, v in data.items()
                if isinstance(v, str) and RE_MARKUP.search(k)
                and len(TOKEN.findall(k)) != len(TOKEN.findall(v))]
    todo = sorted(set(broken) | set(mismatch))
    print(f"строк на переперевод: {len(todo)}")

    if not todo:
        return

    glossary = load_glossary()
    tm_path = HERE / "term_map_quests_google.json"
    term_map = load_term_map(tm_path if tm_path.exists() else None)
    fixer = TermFixer(glossary, term_map) if term_map else None

    tr = Translator(GoogleBackend(), glossary,
                    cache_path=HERE / "cache_google_repair2.json",
                    fixer=fixer, token_fmt="<x_{i}/>")
    variants = tr.translate_many(todo)

    changed = 0
    still_bad = []
    for src, ru_new in zip(todo, variants):
        old = data.get(src, src)
        ok_new = not BROKEN.search(ru_new)
        ok_old = not BROKEN.search(old)
        # разметка в переводе должна совпадать с оригиналом
        marks_new = RE_MARKUP.findall(ru_new)
        marks_src = RE_MARKUP.findall(src)
        ok_marks = marks_new == marks_src
        if ok_new and ok_marks and quality(src, ru_new) >= quality(src, old):
            if ru_new != old:
                data[src] = ru_new
                changed += 1
        elif not ok_old:
            # старое тоже битое — берём новое, даже если оценка ниже
            data[src] = ru_new
            changed += 1
        else:
            still_bad.append(src[:90])

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"исправлено строк: {changed}")
    print(f"осталось спорных: {len(still_bad)}")
    for s in still_bad[:10]:
        print("   ", repr(s))


if __name__ == "__main__":
    main()
