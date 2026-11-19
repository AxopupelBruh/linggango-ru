"""Перевод строк из Java-кода модов через DeepSeek (с большим системным промптом).

Зачем: DeepL Free даёт более низкое качество. Пользователь попросил
использовать DeepSeek с тем же системным промптом, что и для lang-файлов.

Как устроено:
  * бренды (названия модов) маскируются токенами [[0]], [[1]]… — мод обязан
    вернуть их без изменений, поэтому названия модов остаются латиницей;
  * термины глоссария, встречающиеся в строке, передаются подсказками
    (поле terms) — мод сам склоняет их по-русски;
  * §-коды не трогаются, но результат проверяется: если коды разошлись или
    перевод пустой, берётся запасной вариант из DeepL.

Результат: work/ui_strings_ru.json (перезаписывается)
Кэш:     work/cache_deepseek_ui.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from deepseek_backend import DeepSeekBackend  # noqa: E402
from fix_ui_brands import build_brands  # noqa: E402

CODE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
TOKEN = re.compile(r"\[\[(\d+)\]\]")
MAX_TERMS = 8


def term_index(terms: dict[str, str]) -> dict[str, list[str]]:
    """Индекс глоссария по первому слову — быстрый подбор фраз."""
    idx: dict[str, list[str]] = {}
    for k in terms:
        if not k.strip():
            continue
        idx.setdefault(k.split()[0].lower(), []).append(k)
    for v in idx.values():
        v.sort(key=len, reverse=True)
    return idx


def hints_for(text: str, terms: dict[str, str],
              idx: dict[str, list[str]]) -> dict[str, str]:
    """Термины глоссария, реально встречающиеся в строке."""
    out: dict[str, str] = {}
    low = text.lower()
    words = set(re.findall(r"[a-z][a-z'-]{2,}", low))
    for w in words:
        for t in idx.get(w, []):
            if len(out) >= MAX_TERMS:
                break
            if t.lower() in low:
                ru = terms[t]
                if ru and ru != t:
                    out[t] = ru
    return out


class BrandMasker:
    def __init__(self, brands: list[str]):
        self.brands = sorted(brands, key=len, reverse=True)
        pat = "|".join(re.escape(b) for b in self.brands)
        self.re = re.compile(r"(?<![\w])(" + pat + r")(?![\w])", re.IGNORECASE)

    def mask(self, text: str) -> tuple[str, list[str]]:
        found: list[str] = []

        def repl(m: re.Match) -> str:
            found.append(m.group(0))
            return "[[%d]]" % (len(found) - 1)

        return self.re.sub(repl, text), found

    @staticmethod
    def unmask(text: str, found: list[str]) -> str:
        def repl(m: re.Match) -> str:
            i = int(m.group(1))
            return found[i] if i < len(found) else m.group(0)
        return TOKEN.sub(repl, text)


def validate(src: str, ru: str) -> bool:
    if not ru or not ru.strip():
        return False
    if CODE.findall(src) != CODE.findall(ru):
        return False
    if "[[" in ru or "]]" in ru:
        return False
    if re.search(r"\{\d+\}", ru):
        return False
    if ru.strip() == src.strip():
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", type=int, default=-1,
                    help="индекс части (-1 = вся работа)")
    ap.add_argument("--parts", type=int, default=1,
                    help="на сколько частей делить список")
    ap.add_argument("--key-file", default="", help="файл с API-ключом")
    ap.add_argument("--cache-file", default="", help="файл кэша")
    ap.add_argument("--batch", type=int, default=20, help="строк в одном запросе")
    ap.add_argument("--workers", type=int, default=5, help="одновременных запросов")
    ap.add_argument("--no-final", action="store_true",
                    help="не перезаписывать итоговый ui_strings_ru.json")
    args = ap.parse_args()

    src = json.loads((WORK / "ui_strings.json").read_text(encoding="utf-8"))
    deepl_map = json.loads((WORK / "ui_strings_ru_deepl.json").read_text(encoding="utf-8"))
    cur = json.loads((WORK / "ui_strings_ru.json").read_text(encoding="utf-8"))
    deepl_map.update(cur)
    terms = json.loads((WORK / "terms_mined.json").read_text(encoding="utf-8"))
    idx = term_index(terms)
    brands = build_brands()
    masker = BrandMasker(brands)
    print(f"строк: {len(src)}, брендов: {len(brands)}, терминов: {len(terms)}")

    cache_path = Path(args.cache_file) if args.cache_file else WORK / "cache_deepseek_ui.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    # готовим задания
    items: list[dict] = []
    keys: list[str] = []
    for s in src:
        masked, found = masker.mask(s)
        h = hints_for(s, terms, idx)
        key = masked + "\x00" + json.dumps(h, ensure_ascii=False, sort_keys=True)
        items.append({"en": masked, "terms": h})
        keys.append(key)

    # Делим именно НЕПЕРЕВЕДЁННЫЕ строки: иначе пул, чей кусок уже переведён
    # прошлым прогоном, простаивает, а остальные перегружены.
    # Все пулы стартуют с одинаковым кэшем → разбиение одинаковое,
    # дублирования нет.
    pending = [i for i, k in enumerate(keys) if k not in cache]
    if args.parts > 1 and 0 <= args.part < args.parts:
        chunk = (len(pending) + args.parts - 1) // args.parts
        todo_idx = pending[args.part * chunk:(args.part + 1) * chunk]
    else:
        todo_idx = pending
    print(f"в своей части: {len(todo_idx)} строк")

    api_key = ""
    if args.key_file:
        api_key = Path(args.key_file).read_text(encoding="utf-8").strip()
    backend = DeepSeekBackend(api_key=api_key or None)
    batch_size = args.batch
    batches = [todo_idx[i:i + batch_size]
               for i in range(0, len(todo_idx), batch_size)]
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    def work(batch: list[int]) -> None:
        payload = [items[i] for i in batch]
        got = None
        try:
            got = backend.translate_batch_hinted(payload)
        except Exception as e:  # noqa: BLE001
            print(f"  ! батч не удался, пробуем по одной: {str(e)[:120]}", flush=True)
        if got is None:
            # провайдер не тянет крупный запрос — дробим на одиночные строки
            got = []
            for i in batch:
                try:
                    got.append(backend.translate_batch_hinted([items[i]])[0])
                except Exception as e:  # noqa: BLE001
                    print(f"  ! строка не переведена: {str(e)[:100]}", flush=True)
                    got.append(None)
        with lock:
            for i, ru in zip(batch, got):
                if ru:
                    cache[keys[i]] = ru
            done[0] += len(batch)
            if done[0] % 100 < batch_size:
                cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
                rate = done[0] / max(1, time.time() - t0)
                print(f"  ... {done[0]}/{len(todo_idx)}  ({rate:.1f} стр/с)",
                      flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, batches))

    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"переводов получено: {len(cache)}")

    # собираем итог
    result: dict[str, str] = {}
    stats = {"ok": 0, "fallback": 0, "bad": 0}
    for s, key in zip(src, keys):
        ru = cache.get(key)
        if ru:
            # снимаем маску брендов
            masked, found = masker.mask(s)
            ru = masker.unmask(ru, found)
        if ru and validate(s, ru):
            result[s] = ru
            stats["ok"] += 1
        else:
            alt = deepl_map.get(s)
            if alt and validate(s, alt):
                result[s] = alt
                stats["fallback"] += 1
            else:
                stats["bad"] += 1
                if alt:
                    result[s] = alt

    if not args.no_final:
        (WORK / "ui_strings_ru.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"готово: {len(result)}  (DeepSeek: {stats['ok']}, "
          f"запасной DeepL: {stats['fallback']}, без перевода: {stats['bad']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
