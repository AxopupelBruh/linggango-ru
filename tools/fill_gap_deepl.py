"""Закрывает пробелы в словаре переводов через DeepL.

Набор строк из Java-кода модов вырос (после исправления фильтра сканирования),
и часть строк ещё не переведена ни DeepSeek, ни DeepL. Этот скрипт
добирает их через DeepL, чтобы в игре не осталось английских подсказок.
Позже DeepSeek-прогоны перезапишут эти переводы более качественными.

Запуск: python3 fill_gap_deepl.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from deepl_backend import DeepLBackend  # noqa: E402
from fix_java_strings import load_terms, postprocess, translate_all  # noqa: E402
from fix_ui_brands import build_brands  # noqa: E402
from translate_ui_deepseek import BrandMasker, hints_for, term_index, validate  # noqa: E402


def main() -> int:
    src = json.loads((WORK / "ui_strings.json").read_text(encoding="utf-8"))
    deepl_map = json.loads((WORK / "ui_strings_ru_deepl.json").read_text(encoding="utf-8"))
    terms = load_terms()

    # что уже есть
    have = set(deepl_map)
    for p in sorted(WORK.glob("cache_deepseek_ui*.json")):
        cache = json.loads(p.read_text(encoding="utf-8"))
        masker = BrandMasker(build_brands())
        idx = term_index(json.loads((WORK / "terms_mined.json").read_text(encoding="utf-8")))
        for s in src:
            if s in have:
                continue
            masked, found = masker.mask(s)
            h = hints_for(s, terms, idx)
            key = masked + "\x00" + json.dumps(h, ensure_ascii=False, sort_keys=True)
            if key in cache:
                have.add(s)

    todo = [s for s in src if s not in have]
    print(f"строк всего: {len(src)}, уже есть: {len(src) - len(todo)}, добрать: {len(todo)}")

    if todo:
        backend = DeepLBackend()
        cache_path = WORK / "cache_deepl_gap.json"
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        fresh = [s for s in todo if s not in cache]
        print(f"в кэше: {len(todo) - len(fresh)}, переводим: {len(fresh)}")
        # переводим маскированные (без брендов) строки через translate_all —
        # он режет строку по §-кодам и возвращает их на место
        masker = BrandMasker(build_brands())
        masked_map = {s: masker.mask(s)[0] for s in fresh}
        uniq = list(dict.fromkeys(masked_map.values()))
        got_map: dict[str, str] = {}
        for i in range(0, len(uniq), backend.max_items):
            batch = uniq[i:i + backend.max_items]
            try:
                got = translate_all(batch, backend, terms)
            except Exception as e:  # noqa: BLE001
                print(f"  ! ошибка на батче {i}: {e}")
                break
            got_map.update(got)
            print(f"  ... {i + len(batch)}/{len(uniq)}", flush=True)
        for s in fresh:
            m = masked_map[s]
            if m in got_map:
                cache[s] = got_map[m]
            if i % 400 < backend.max_items:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0),
                                      encoding="utf-8")
                print(f"  ... {i + len(batch)}/{len(fresh)}", flush=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")

        # восстанавливаем бренды и проверяем результат
        for s in todo:
            ru = cache.get(s)
            if not ru:
                continue
            _masked, found = masker.mask(s)
            ru = masker.unmask(ru, found)
            ru = postprocess(s, ru)
            if validate(s, ru):
                deepl_map[s] = ru

    (WORK / "ui_strings_ru_deepl.json").write_text(
        json.dumps(deepl_map, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"карта переводов DeepL: {len(deepl_map)} строк")
    return 0


if __name__ == "__main__":
    sys.exit(main())
