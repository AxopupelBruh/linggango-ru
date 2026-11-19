"""Собирает карту «термин → как его называет переводчик».

Нужна, чтобы после перевода прозы починить терминологию: переводчик называет
предметы по-своему («Warden» → «надзиратель»), а игрок в GUI видит официальные
названия («Хранитель»). Здесь мы переводим каждый термин отдельно и запоминаем
оба варианта.

У DeepL и Google свои варианты, поэтому карта строится отдельно для каждого.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tr_engine import DeepLBackend, GoogleBackend, load_glossary  # noqa: E402

HERE = Path(__file__).parent
WORK = HERE / "work"


def terms_in_sources(sources: list[str]) -> list[tuple[str, str]]:
    """Сильные термины глоссария, реально встречающиеся в исходниках."""
    glossary = load_glossary()
    strong = {en.lower(): val["ru"] for en, val in glossary.items()
              if isinstance(val, dict) and val.get("strong") and val.get("ru")}
    orig = {en.lower(): en for en, val in glossary.items()
            if isinstance(val, dict) and val.get("strong") and val.get("ru")}
    found: dict[str, str] = {}
    for src in sources:
        low = src.lower()
        for key, ru in strong.items():
            if len(key) < 4:
                continue
            if key in low and key not in found:
                found[key] = ru
    return [(orig.get(k, k), v) for k, v in found.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    choices=["quests", "kubejs", "mods", "patchouli", "extra"])
    ap.add_argument("--backend", default="deepl", choices=["deepl", "google"])
    args = ap.parse_args()

    data = json.loads((WORK / f"{args.source}.json").read_text(encoding="utf-8"))
    terms = terms_in_sources(list(data.keys()))
    print(f"источник={args.source} бэкенд={args.backend}: {len(terms)} сильных терминов",
          flush=True)

    if args.backend == "deepl":
        keys = [ln.strip() for ln in (HERE / ".deepl_keys").read_text(encoding="utf-8").splitlines()
                if ln.strip()]
        backend = DeepLBackend(keys)
    else:
        backend = GoogleBackend()

    out = {}
    batch: list[tuple[str, str]] = []
    for i, (en, ru) in enumerate(terms):
        batch.append((en, ru))
        if len(batch) >= 50 or i == len(terms) - 1:
            try:
                res = backend.translate_batch([e for e, _ in batch])
            except Exception as exc:  # noqa: BLE001
                print("ошибка батча:", exc, flush=True)
                res = [""] * len(batch)
            for (en_text, ru_text), translated in zip(batch, res):
                out[en_text] = {"ru": ru_text, "deepl": translated}
            batch = []
            if i % 500 < 50:
                print(f"  ... {i + 1}/{len(terms)}", flush=True)

    path = HERE / f"term_map_{args.source}_{args.backend}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    diff = sum(1 for v in out.values()
               if v["deepl"].strip().lower() != v["ru"].strip().lower())
    print(f"готово: {len(out)} терминов, {diff} расходятся с каноном → {path.name}")


if __name__ == "__main__":
    main()
