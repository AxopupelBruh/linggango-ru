"""Доперевод проблемных строк квестов.

В основном проходе часть строк попала в кэш в неудачном виде (переводчик
вернул их без перевода или потерял невидимые разделители). Здесь они
переводятся заново — со свежим кэшем и другим форматом плейсхолдера,
который переводчик не «склеивает».

Результат подставляется в work/quests_ru.json только если он лучше прежнего.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
sys.path.insert(0, str(HERE))
from fixup import TermFixer, load_term_map  # noqa: E402
from tr_engine import GoogleBackend, Translator, load_glossary, quality  # noqa: E402

# форматы пробуем по очереди — какой лучше справится
FORMATS = ["<x_{i}/>", "☐{i}☐", "~{i}~", "*{i}*", "[[{i}]]"]


def main() -> None:
    manual_path = WORK / "quests_manual.json"
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    problems = sorted({e["src"] for e in manual if e.get("src")})
    print(f"проблемных строк: {len(problems)}")
    if not problems:
        return

    ru = json.loads((WORK / "quests_ru.json").read_text(encoding="utf-8"))
    glossary = load_glossary()
    tm_path = HERE / "term_map_quests_google.json"
    term_map = load_term_map(tm_path if tm_path.exists() else None)
    fixer = TermFixer(glossary, term_map) if term_map else None

    backend = GoogleBackend()
    best: dict[str, str] = {}
    for fmt in FORMATS:
        tr = Translator(backend, glossary,
                        cache_path=HERE / f"cache_google_fix_{abs(hash(fmt)) % 9999}.json",
                        fixer=fixer, token_fmt=fmt)
        variants = tr.translate_many(problems)
        improved = 0
        for src, ru_new in zip(problems, variants):
            old = best.get(src, ru.get(src, src))
            if quality(src, ru_new) > quality(src, old):
                best[src] = ru_new
                improved += 1
        print(f"  формат {fmt}: улучшено {improved}")
        if improved == len(problems):
            break

    changed = 0
    for src, ru_new in best.items():
        if quality(src, ru_new) > quality(src, ru.get(src, src)):
            ru[src] = ru_new
            changed += 1
    (WORK / "quests_ru.json").write_text(
        json.dumps(ru, ensure_ascii=False, indent=1), encoding="utf-8")

    manual = [e for e in manual
              if quality(e["src"], ru.get(e["src"], e["src"])) < 3]
    manual_path.write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"обновлено строк: {changed}, в очереди осталось: {len(manual)}")


if __name__ == "__main__":
    main()
