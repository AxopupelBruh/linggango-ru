"""Перевод lang-ключей, показываемых по-английски, через DeepSeek (качественнее DeepL).

Бренды маскируются токенами {N}, глоссарий подсказывается модельу hints_for(),
плейсхолдеры %s/%d контролируются проверкой.

Запуск: python3 fill_lang_gap_deepseek.py [--part N --parts M]
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
from translate_ui_deepseek import BrandMasker, hints_for, term_index  # noqa: E402

PH = re.compile(r"%(?:\d+\$)?[-+0-9.#]*[sdf]|%%|%n")
WORDS = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
URL = re.compile(r"^\s*https?://")


def translatable(s: str) -> bool:
    if URL.search(s):
        return False
    if "$(" in s and not WORDS.search(re.sub(r"\$\([^)]*\)", "", s)):
        return False
    if len(WORDS.findall(s)) == 0:
        return False
    # только коды/символы/плейсхолдеры — переводить нечего
    stripped = PH.sub("", s)
    stripped = re.sub(r"§[0-9a-fk-orA-FK-OR]", "", stripped)
    stripped = re.sub(r"[^\w\s]", "", stripped, flags=re.UNICODE)
    if len(WORDS.findall(stripped)) == 0:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", type=int, default=-1)
    ap.add_argument("--parts", type=int, default=1)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--key-file", default="")
    args = ap.parse_args()

    need = json.loads((WORK / "lang_need.json").read_text(encoding="utf-8"))
    uniq = list(dict.fromkeys(x[2] for x in need))
    todo = [s for s in uniq if translatable(s)]
    print(f"пропусков: {len(need)}, уникальных: {len(uniq)}, к переводу: {len(todo)}")

    terms = json.loads((WORK / "terms_mined.json").read_text(encoding="utf-8"))
    idx = term_index(terms)
    masker = BrandMasker(build_brands())

    items = []
    keys = []
    for s in todo:
        masked, found = masker.mask(s)
        h = hints_for(s, terms, idx)
        items.append({"en": masked, "terms": h, "__orig": s, "__found": found})
        keys.append(masked + "\x00" + json.dumps(h, ensure_ascii=False, sort_keys=True))

    cache_path = WORK / "cache_lang_gap_deepseek.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    pending = [i for i, k in enumerate(keys) if k not in cache]
    if args.parts > 1 and 0 <= args.part < args.parts:
        chunk = (len(pending) + args.parts - 1) // args.parts
        pending = pending[args.part * chunk:(args.part + 1) * chunk]
    print(f"в своей части: {len(pending)}")

    api_key = ""
    if args.key_file:
        api_key = Path(args.key_file).read_text(encoding="utf-8").strip()
    backend = DeepSeekBackend(api_key=api_key or None)

    batches = [pending[i:i + args.batch] for i in range(0, len(pending), args.batch)]
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    def work(batch: list[int]) -> None:
        payload = [{"en": items[i]["en"], "terms": items[i]["terms"]} for i in batch]
        got = None
        try:
            got = backend.translate_batch_hinted(payload)
        except Exception as e:  # noqa: BLE001
            print(f"  ! батч: {str(e)[:110]}", flush=True)
        if got is None:
            got = []
            for i in batch:
                try:
                    got.append(backend.translate_batch_hinted([{"en": items[i]["en"],
                                                             "terms": items[i]["terms"]}])[0])
                except Exception as e:  # noqa: BLE001
                    print(f"  ! строка: {str(e)[:90]}", flush=True)
                    got.append(None)
        with lock:
            for i, ru in zip(batch, got):
                if ru:
                    cache[keys[i]] = ru
            done[0] += len(batch)
            if done[0] % 40 < args.batch:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
                print(f"  ... {done[0]}/{len(pending)}  "
                      f"({done[0] / max(1, time.time() - t0):.2f} стр/с)", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, batches))

    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"в кэше: {len(cache)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
