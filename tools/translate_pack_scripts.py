"""Перевод английских строк, которые КУБЕДЖС-скрипты самого пака добавляют
в тултипы (tooltip_additions.js и подобные).

Проблема: `event.add([...], '§8Some text')` добавляет строку в тултип при любой
локализации — в ru_ru она остаётся английской. Наш переводчик (KubeJS) такие
строки тоже переводит, если они есть в словаре.

Строки из lang.js не трогаем: там для ru_ru уже есть готовые переименования.

Результат: work/pack_script_ru.json = {английская строка: русский перевод}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
KUBE = INSTANCE / "kubejs"

sys.path.insert(0, str(HERE))
from deepseek_backend import DeepSeekBackend  # noqa: E402
from translate_ui_deepseek import BrandMasker, hints_for, term_index  # noqa: E402
from fix_ui_brands import build_brands  # noqa: E402

STR_RE = re.compile(r"'([^'\\\n]{8,250})'|\"([^\"\\\n]{8,250})\"")


def extract() -> dict[str, str]:
    out: dict[str, str] = {}
    for folder in ("client_scripts", "server_scripts", "startup_scripts"):
        d = KUBE / folder
        if not d.exists():
            continue
        for f in sorted(d.glob("*.js")):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for m in STR_RE.finditer(txt):
                s = m.group(1) or m.group(2)
                if not re.search(r"[A-Za-z]{3}", s):
                    continue
                if re.search(r"[а-яёА-ЯЁ]", s):
                    continue
                if re.search(r"[/\\{}<>=]", s):
                    continue
                if " " not in s:
                    continue
                out.setdefault(s, f"{folder}/{f.name}")
    return out


def main() -> int:
    strings = extract()
    # выкидываем то, что уже переведено в lang.js (там есть ru_ru-секция)
    lang = (KUBE / "client_scripts" / "lang.js")
    known_ru: set[str] = set()
    if lang.exists():
        txt = lang.read_text(encoding="utf-8", errors="ignore")
        ru_part = txt.split("ru_ru", 1)[-1]
        for m in STR_RE.finditer(ru_part):
            s = m.group(1) or m.group(2)
            if re.search(r"[а-яёА-ЯЁ]", s):
                known_ru.add(s)
    # названия предметов из en_us-секции lang.js — переименованы в ru_ru
    en_part = txt.split('"en_us"', 1)[-1].split('"ru_ru"', 1)[0] if lang.exists() else ""
    names_in_lang: set[str] = set()
    for m in STR_RE.finditer(en_part):
        s = m.group(1) or m.group(2)
        if re.search(r"[A-Za-z]{3}", s) and " " in s:
            names_in_lang.add(s)

    todo = {s: f for s, f in strings.items()
            if s not in known_ru and s not in names_in_lang}
    print(f"строк всего: {len(strings)}, к переводу: {len(todo)}")

    terms = json.loads((WORK / "terms_mined.json").read_text(encoding="utf-8"))
    idx = term_index(terms)
    masker = BrandMasker(build_brands())

    items = []
    keys = list(todo)
    for s in keys:
        m, _f = masker.mask(s)
        items.append({"en": m, "terms": hints_for(s, terms, idx)})

    cache_path = WORK / "cache_deepseek_pack.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    backend = DeepSeekBackend()
    out_map: dict[str, str] = {}
    todo_idx = [i for i, it in enumerate(items)
                if it["en"] + "\x00" + json.dumps(it["terms"], ensure_ascii=False,
                                                 sort_keys=True) not in cache]
    print(f"в кэше: {len(items) - len(todo_idx)}, переводим: {len(todo_idx)}")
    for i in range(0, len(todo_idx), 20):
        batch = todo_idx[i:i + 20]
        payload = [items[j] for j in batch]
        try:
            got = backend.translate_batch_hinted(payload)
        except Exception as e:  # noqa: BLE001
            print(f"  ! батч {i}: {e}")
            break
        for j, ru in zip(batch, got):
            key = items[j]["en"] + "\x00" + json.dumps(items[j]["terms"],
                                                      ensure_ascii=False, sort_keys=True)
            cache[key] = ru
        if i % 200 < 20:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0),
                                  encoding="utf-8")
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")

    for s in keys:
        it = {"en": masker.mask(s)[0]}
        it["terms"] = hints_for(s, terms, idx)
        key = it["en"] + "\x00" + json.dumps(it["terms"], ensure_ascii=False, sort_keys=True)
        ru = cache.get(key)
        if not ru:
            continue
        ru = masker.unmask(ru, masker.mask(s)[1])
        if ru.strip() and ru.strip() != s.strip():
            out_map[s] = ru

    (WORK / "pack_script_ru.json").write_text(
        json.dumps(out_map, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"переведено: {len(out_map)}")
    for s, ru in list(out_map.items())[:12]:
        print(f"  {s[:60]!r}\n   → {ru[:60]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
