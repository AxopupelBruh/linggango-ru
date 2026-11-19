"""Переводит собранные строки и складывает результат в work/<source>_ru.json.

  python3 run.py --source quests --backend deepl
  python3 run.py --source mods --backend google --limit 40 --demo
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fixup import TermFixer, load_term_map  # noqa: E402
from tr_engine import (DeepLBackend, GoogleBackend, Translator,  # noqa: E402
                       load_glossary, quality)

HERE = Path(__file__).parent
WORK = HERE / "work"
CHUNK = 200  # строк за один проход translate_many


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    choices=["quests", "kubejs", "mods", "patchouli", "extra"])
    ap.add_argument("--out", default="", help="имя выходного файла (work/<out>.json)")
    ap.add_argument("--backend", default="deepl", choices=["deepl", "google"])
    ap.add_argument("--limit", type=int, default=0, help="0 = без ограничения")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--demo", action="store_true", help="только показать примеры")
    ap.add_argument("--key-file", default=".deepl_keys", help="файл с ключами DeepL")
    ap.add_argument("--token-fmt", default="", help="формат плейсхолдера, напр. %%%%{i}%%%%")
    ap.add_argument("--cache", default="", help="имя файла кэша")
    args = ap.parse_args()

    data = json.loads((WORK / f"{args.source}.json").read_text(encoding="utf-8"))
    items = list(data.items())
    if args.offset:
        items = items[args.offset:]
    if args.limit:
        items = items[:args.limit]

    glossary = load_glossary()
    if args.backend == "deepl":
        keys = [ln.strip() for ln in
                (HERE / args.key_file).read_text(encoding="utf-8").splitlines()
                if ln.strip()]
        backend = DeepLBackend(keys)
    else:
        backend = GoogleBackend()

    tm_path = HERE / f"term_map_{args.source}_{args.backend}.json"
    if not tm_path.exists():
        tm_path = HERE / f"term_map_{args.source}.json"
    term_map = load_term_map(tm_path)
    fixer = TermFixer(glossary, term_map) if term_map else None
    cache_name = args.cache or f"cache_{args.backend}.json"
    tr = Translator(backend, glossary, cache_path=HERE / cache_name,
                    fixer=fixer,
                    token_fmt=args.token_fmt.replace("%%", "%") if args.token_fmt else None)

    print(f"источник={args.source} бэкенд={args.backend} строк={len(items)} "
          f"символов={sum(len(k) for k, _ in items)} глоссарий={len(glossary)} "
          f"карта терминов={len(term_map)}", flush=True)

    out_path = WORK / f"{args.out or args.source}_ru.json"
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    manual_path = WORK / f"{args.out or args.source}_manual.json"
    manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else []

    t0 = time.time()
    todo = [(src, where) for src, where in items if src not in done]
    for start in range(0, len(todo), CHUNK):
        chunk = todo[start:start + CHUNK]
        before = len(tr.manual)
        sources = [src for src, _ in chunk]
        translations = tr.translate_many(sources)
        for (src, where), ru in zip(chunk, translations):
            done[src] = ru
        for entry in tr.manual[before:]:
            entry["where"] = next((w for s, w in chunk if s == entry["src"]), [])
            manual.append(entry)
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        manual_path.write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")
        n = start + len(chunk)
        rate = n / max(time.time() - t0, 0.001)
        print(f"  ... {n}/{len(todo)}  {rate:.0f} строк/с  кэш={len(tr.cache)} "
              f"очередь={len(manual)}", flush=True)
        if args.demo and start == 0:
            for (src, where), ru in list(zip(chunk, translations))[:12]:
                print(f"\n  где: {where[0]}")
                print(f"  EN: {src[:200]}")
                print(f"  RU: {ru[:200]}")

    print(f"\nготово: {len(done)} переведено, {len(manual)} в ручную очередь, "
          f"{time.time() - t0:.0f} с")
    print("статистика:", dict(tr.stats))

    # ---- ремонтный проход -------------------------------------------------
    # DeepL не переводит текст рядом с плейсхолдерами вида [[N]] и иногда теряет
    # их. Переводим такие строки заново с другим форматом плейсхолдера
    # (%%N%%), который DeepL воспринимает нейтрально, и оставляем лучший вариант.
    problems = sorted({e["src"] for e in manual if e.get("src")})
    if problems:
        print(f"\nремонтный проход: {len(problems)} проблемных строк", flush=True)
        repair = Translator(
            backend, glossary,
            cache_path=HERE / f"cache_{args.backend}_repair.json",
            fixer=fixer, token_fmt="%%{i}%%")
        fixed = 0
        for start in range(0, len(problems), CHUNK):
            chunk = problems[start:start + CHUNK]
            variants = repair.translate_many(chunk)
            for src, ru in zip(chunk, variants):
                old = done.get(src, src)
                if quality(src, ru) > quality(src, old):
                    done[src] = ru
                    fixed += 1
            print(f"  ... {start + len(chunk)}/{len(problems)}, исправлено {fixed}", flush=True)
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        manual = [e for e in manual
                  if quality(e["src"], done.get(e["src"], e["src"])) >= 0
                  and done.get(e["src"], e["src"]) != e["src"]]
        manual_path.write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"ремонтный проход: исправлено {fixed}, в очереди осталось {len(manual)}")


if __name__ == "__main__":
    main()
