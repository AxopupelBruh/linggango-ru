"""Перевод строк, найденных в runtime-логе KubeJS ([RU-TT]).

Статический скан классов не ловит всё (строки из enum'ов, конфигов, служебных
классов). Когда игрок наводит курсор, переводчик пишет неизвестные строки в
logs/kubejs/client.log с меткой [RU-TT] — этот скрипт берёт их оттуда,
переводит и добавляет в словарь.

Запуск: python3 translate_runtime_missing.py [--log путь] [--deepl]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
ROOT = INSTANCE
LOG = ROOT / "logs" / "kubejs" / "client.log"

sys.path.insert(0, str(HERE))
from deepseek_backend import DeepSeekBackend  # noqa: E402
from deepl_backend import DeepLBackend  # noqa: E402
from fix_java_strings import load_terms, postprocess, translate_all  # noqa: E402
from fix_ui_brands import build_brands  # noqa: E402
from translate_ui_deepseek import BrandMasker, hints_for, term_index  # noqa: E402

# что переводить бессмысленно
SKIP = [
    (re.compile(r"^C\d{3} — "), "звук (субтит)"),
    (re.compile(r"^https?://"), "URL"),
    (re.compile(r"^painting\."), "ключ картины"),
    (re.compile(r"^[a-z_]+\.[a-z_0-9.]+$"), "ключ перевода (уже в lang)"),
]


def collect(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    out: list[str] = []
    for m in re.finditer(r"\[RU-TT\] (.*)$", text, re.M):
        s = m.group(1).strip()
        if s and s not in out:
            out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(LOG))
    ap.add_argument("--deepl", action="store_true", help="переводить через DeepL")
    ap.add_argument("--batch", type=int, default=15)
    args = ap.parse_args()

    raw = collect(Path(args.log))
    todo = []
    for s in raw:
        if any(rx.search(s) for rx, _ in SKIP):
            continue
        todo.append(s)
    print(f"строк в логе: {len(raw)}, к переводу: {len(todo)}")

    terms = json.loads((WORK / "terms_mined.json").read_text(encoding="utf-8"))
    idx = term_index(terms)
    masker = BrandMasker(build_brands())
    gl_terms = load_terms()

    out_path = WORK / "runtime_missing_ru.json"
    cache_path = WORK / "cache_runtime_missing.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    todo = [s for s in todo if s not in cache]
    print(f"в кэше: {len(raw) - len(todo)}, переводим: {len(todo)}")

    if todo and not args.deepl:
        keys = [p.read_text(encoding="utf-8").strip()
                for p in sorted(HERE.glob(".deepseek_key*"))]
        print(f"ключей DeepSeek: {len(keys)}")
        chunks = [todo[i::len(keys)] for i in range(len(keys))]
        lock = threading.Lock()

        def work(idx_chunk: tuple[int, list[str]]) -> None:
            i, chunk = idx_chunk
            backend = DeepSeekBackend(api_key=keys[i])
            for j in range(0, len(chunk), args.batch):
                batch = chunk[j:j + args.batch]
                items = []
                for s in batch:
                    m, _f = masker.mask(s)
                    items.append({"en": m, "terms": hints_for(s, terms, idx)})
                try:
                    got = backend.translate_batch_hinted(items)
                except Exception as e:  # noqa: BLE001
                    print(f"  ! ключ {i}: {str(e)[:100]}", flush=True)
                    continue
                with lock:
                    for s, ru in zip(batch, got):
                        if ru:
                            cache[s] = ru
                    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0),
                                          encoding="utf-8")
                    print(f"  ключ {i}: {len(cache)} в кэше", flush=True)

        with ThreadPoolExecutor(max_workers=len(keys)) as ex:
            list(ex.map(work, enumerate(chunks)))

    if todo and args.deepl:
        backend = DeepLBackend()
        masked = {s: masker.mask(s)[0] for s in todo}
        got = translate_all(list(dict.fromkeys(masked.values())), backend, gl_terms)
        for s, m in masked.items():
            if m in got:
                cache[s] = got[m]
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0),
                              encoding="utf-8")

    # собираем итог
    result: dict[str, str] = {}
    for s, ru in cache.items():
        _m, found = masker.mask(s)
        ru = masker.unmask(ru, found)
        ru = postprocess(s, ru)
        if ru.strip() and ru.strip() != s.strip():
            result[s] = ru
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"переведено и сохранено: {len(result)} → {out_path}")
    for s, ru in list(result.items())[:10]:
        print(f"   {s[:70]!r}\n    → {ru[:70]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
