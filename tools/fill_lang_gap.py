"""Дозаполняет lang-ключи, которые в игре показываются по-английски.

Мы собрали список таких ключей (work/lang_need.json: [namespace, key, english]).
Переводим уникальные английские строки через DeepL (бренды маскируются,
плейсхолдеры %s/%d защищаются) и пишем результат в work/mods_ru.json —
это тот же словарь, который читает build_resourcepack.py, поэтому обычная
пересборка ресурспака подхватит переводы.

Запуск: python3 fill_lang_gap.py [--deepl]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from deepl_backend import DeepLBackend  # noqa: E402
from fix_java_strings import load_terms, translate_all  # noqa: E402
from fix_ui_brands import build_brands  # noqa: E402
from translate_ui_deepseek import BrandMasker  # noqa: E402

# плейсхолдеры формата: %s %d %f %.2f %% %1$s
PH = re.compile(r"%(?:\d+\$)?[-+0-9.#]*[sdf]|%%|%n")
PH_TOKEN = "⸤{}⸥"

# строки без слов — переводить нечего
WORDS = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def protect(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def repl(m: re.Match) -> str:
        found.append(m.group(0))
        return PH_TOKEN.format(len(found) - 1)

    return PH.sub(repl, text), found


def restore(text: str, found: list[str]) -> str:
    def repl(m: re.Match) -> str:
        i = int(m.group(1))
        return found[i] if i < len(found) else m.group(0)

    return re.sub(r"⸤(\d+)⸥", repl, text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deepl", action="store_true", help="через DeepL (иначе DeepSeek)")
    ap.add_argument("--terms", default="terms_merged",
                    help="файл глоссария в work/ (terms_merged — с официальной ванилью)")
    args = ap.parse_args()

    need = json.loads((WORK / "lang_need.json").read_text(encoding="utf-8"))
    print(f"пропусков: {len(need)}")

    uniq = list(dict.fromkeys(x[2] for x in need))
    # переводим только те, где есть слова
    todo = [s for s in uniq if len(WORDS.findall(s)) >= 1 and len(s) > 1]
    skip = [s for s in uniq if s not in todo]
    print(f"уникальных строк: {len(uniq)}, к переводу: {len(todo)}, пропуск: {len(skip)}")

    masker = BrandMasker(build_brands())
    terms_path = WORK / f"{args.terms}.json"
    if terms_path.exists():
        terms = json.loads(terms_path.read_text(encoding="utf-8"))
        terms = {k: v for k, v in terms.items()
                 if v.strip() and not re.search(r"[.,;:]$", v.strip())}
    else:
        terms = load_terms()
    print(f"глоссарий: {len(terms)} терминов ({args.terms})")

    # официальная ваниль — точные совпадения берём без обращения к API
    vanilla = {}
    vpath = WORK / "vanilla_terms.json"
    if vpath.exists():
        vanilla = json.loads(vpath.read_text(encoding="utf-8"))

    out: dict[str, str] = {}
    cache_path = WORK / "cache_lang_gap.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    pending = [s for s in todo if s not in cache]
    print(f"в кэше: {len(todo) - len(pending)}, переводим: {len(pending)}")

    # точные совпадения с официальной ванилью — без API
    for s in list(pending):
        v = vanilla.get(s)
        if v and re.search(r"[а-яёА-ЯЁ]", v) and PH.findall(s) == PH.findall(v):
            cache[s] = v
    pending = [s for s in pending if s not in cache]
    print(f"после точных совпадений с ванилью осталось: {len(pending)}")

    if pending:
        # маскируем и бренды, и плейсхолдеры
        prepared: dict[str, tuple[str, list[str], list[str]]] = {}
        for s in pending:
            masked_brands, brands = masker.mask(s)
            prot, phs = protect(masked_brands)
            prepared[s] = (prot, brands, phs)

        if args.deepl:
            backend = DeepLBackend()
            got = translate_all([v[0] for v in prepared.values()], backend, terms)
        else:
            from deepseek_backend import DeepSeekBackend
            backend = DeepSeekBackend()
            items = [{"en": v[0], "terms": {}} for v in prepared.values()]
            res = backend.translate_batch_hinted(items)
            got = {}
            for s, r in zip(prepared.keys(), res):
                if r:
                    got[s] = r
        # translate_all возвращает dict по исходной строке
        if isinstance(got, list):
            got = dict(zip([v[0] for v in prepared.values()], got))

        for s, (prot, brands, phs) in prepared.items():
            ru = got.get(prot)
            if not ru:
                continue
            ru = restore(ru, phs)
            ru = masker.unmask(ru, brands)
            # проверки
            if PH.findall(s) != PH.findall(ru):
                continue
            if not re.search(r"[а-яёА-ЯЁ]", ru):
                continue
            if ru.strip() == s.strip():
                continue
            cache[s] = ru

        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                              encoding="utf-8")

    # пишем в основной словарь
    mods_ru_path = WORK / "mods_ru.json"
    mods_ru = json.loads(mods_ru_path.read_text(encoding="utf-8"))
    added = 0
    for s, ru in cache.items():
        if s not in mods_ru:
            mods_ru[s] = ru
            added += 1
        elif mods_ru[s] == s and ru != s:
            mods_ru[s] = ru
            added += 1
    mods_ru_path.write_text(json.dumps(mods_ru, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(f"в словарь добавлено: {added} (всего {len(mods_ru)})")

    filled = 0
    for ns, key, en in need:
        ru = cache.get(en) or mods_ru.get(en)
        if ru and ru != en:
            filled += 1
    print(f"закрыто ключей: {filled} из {len(need)}")
    for s, ru in list(cache.items())[:15]:
        print(f"   {s[:60]!r}\n    → {ru[:60]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
