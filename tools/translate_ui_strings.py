"""Перевод расширенного словаря строк, зашитых в Java-код модов.

Вход:  work/ui_strings.json  (work/scan_ui_strings.py)
Выход: work/ui_strings_ru.json = {английская строка: русский перевод}

Приоритет источников:
  1. work/java_strings_ru.json — уже переведённые 664 строки (согласовано).
  2. work/mods_ru.json         — точный матч в карте пакета (согласованность
     с ресурспаком: те же формулировки, что и в lang-файлах).
  3. DeepL API                 — всё остальное.

Кэш: work/cache_deepl.json (общий с fix_java_strings.py).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from deepl_backend import DeepLBackend  # noqa: E402
from fix_java_strings import (  # noqa: E402
    CODE, load_terms, postprocess, translate_all, validate,
)


def main() -> int:
    src = json.loads((WORK / "ui_strings.json").read_text(encoding="utf-8"))
    old = json.loads((WORK / "java_strings_ru.json").read_text(encoding="utf-8"))
    mods_map = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    terms = load_terms()

    cache: dict[str, str] = {}
    cache_path = WORK / "cache_deepl.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    result: dict[str, str] = {}
    todo: list[str] = []
    for s in src:
        if s in old:
            result[s] = old[s]
        elif s in mods_map:
            ru = mods_map[s]
            if ru and ru != s:
                result[s] = ru
            else:
                todo.append(s)
        else:
            todo.append(s)

    print(f"строк всего: {len(src)}")
    print(f"из прошлого прогона: {sum(1 for s in src if s in old)}")
    print(f"из карты пакета: {sum(1 for s in result if s not in old)}")
    print(f"к переводу: {len(todo)}")

    if todo:
        backend = DeepLBackend()
        # сначала переводим только те, чего нет в кэше
        fresh = [s for s in todo if s not in cache]
        print(f"в кэше: {len(todo) - len(fresh)}, реально переводим: {len(fresh)}")

        done = 0
        for i in range(0, len(fresh), backend.max_items):
            batch = fresh[i:i + backend.max_items]
            try:
                got = backend.translate(batch)
            except Exception as e:  # сеть/лимит — не теряем прогресс
                print(f"  ошибка на батче {i}: {e}")
                break
            for en, ru in zip(batch, got):
                cache[en] = ru
            done += len(batch)
            if (i // backend.max_items) % 10 == 0:
                print(f"  {done}/{len(fresh)}")
                cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    # собираем итог, чистим артефакты, отбрасываем совпадения с оригиналом
    bad = 0
    for s in todo:
        ru = cache.get(s)
        if not ru:
            continue
        ru = postprocess(s, ru)
        err = validate(s, ru)
        if err:
            bad += 1
            continue
        if ru.strip() == s.strip():
            continue
        result[s] = ru

    (WORK / "ui_strings_ru.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    cyr = sum(1 for v in result.values() if re.search(r"[а-яёА-ЯЁ]", v))
    print(f"\nготово: {len(result)} строк, с кириллицей: {cyr}, отброшено: {bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
