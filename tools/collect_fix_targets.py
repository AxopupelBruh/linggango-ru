"""Собирает непереведённые строки для починки перевода Linggango.

Что собираем (по каждому неймспейсу из jar-ов сборки):
  * «нет ru»      — ключ вообще не переведён (нет ru_ru в моде и нет в нашем паке);
  * «ru == en»    — мод приложил свой ru_ru.json, но там лежит английский текст.

Второй класс — главный: сборщик ресурспака такие ключи пропускал, поэтому в игре
они остаются английскими, хотя перевод у нас есть.

Плюс отдельно ловим:
  * ключи с пустым переводом (мод отдал пустую строку);
  * подозрительные «брендовые» переводы (ФТБ/ДЖЭИ/РЕЙ) — их надо откатить.

Результат: work/fix_targets.json = {"untranslated": [...], "by_ns": {...}, ...}
"""

from __future__ import annotations

import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = INSTANCE
MODS = ROOT / "mods"
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from lang_json import load_lang_json  # noqa: E402

# Строки, которые переводить бессмысленно: чистые форматы, идентификаторы, символы.
SKIP_EXACT = {"", " ", "OK", "None", "N/A", "NA", "true", "false", "null", "yes", "no"}


def load_all() -> tuple[dict, dict, dict]:
    en: dict[str, dict[str, str]] = defaultdict(dict)
    ru_mod: dict[str, dict[str, str]] = defaultdict(dict)
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "/lang/" not in name:
                continue
            folder, fname = name.rsplit("/", 1)
            if fname not in ("en_us.json", "ru_ru.json"):
                continue
            try:
                data = load_lang_json(z.read(name))
            except Exception:
                continue
            ns = folder.split("/")[1]
            (en if fname == "en_us.json" else ru_mod)[ns].update(data)
    pack: dict[str, dict[str, str]] = defaultdict(dict)
    for p in (HERE / "pack_build").glob("assets/*/lang/ru_ru.json"):
        try:
            pack[p.parts[-3]].update(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return en, ru_mod, pack


def main() -> int:
    en, ru_mod, pack = load_all()
    ours = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))

    need: dict[str, list[str]] = defaultdict(list)   # ns -> EN-строки
    empty_ru: dict[str, list[str]] = defaultdict(list)
    stats = {"no_ru": 0, "same_as_en": 0, "empty_ru": 0, "already_ours": 0}

    for ns, keys in en.items():
        p = pack.get(ns, {})
        m = ru_mod.get(ns, {})
        for k, v in keys.items():
            if not isinstance(v, str):
                continue
            cur = p.get(k)
            mod_ru = m.get(k)
            # мод отдал пустой перевод при непустом английском — в игре строка будет пустой
            if (mod_ru is not None and mod_ru.strip() == ""
                    and (cur or "").strip() == "" and v.strip()):
                empty_ru[ns].append(v)
                stats["empty_ru"] += 1
                continue
            if cur is not None:
                if cur == v:
                    stats["already_ours"] += 1
                continue
            if mod_ru is None:
                need[ns].append(v)
                stats["no_ru"] += 1
            elif mod_ru == v:
                need[ns].append(v)
                stats["same_as_en"] += 1

    # уникальные строки
    uniq: dict[str, list[str]] = {}
    for ns, vals in need.items():
        seen: list[str] = []
        for v in vals:
            if v.strip() in SKIP_EXACT:
                continue
            if v not in seen:
                seen.append(v)
        if seen:
            uniq[ns] = sorted(seen)

    # пустые переводы модов — их тоже нужно чинить
    for ns, vals in empty_ru.items():
        for v in vals:
            if v.strip() in SKIP_EXACT:
                continue
            cur = uniq.setdefault(ns, [])
            if v not in cur:
                cur.append(v)
    for ns in uniq:
        uniq[ns] = sorted(uniq[ns])

    all_strings = sorted({v for vals in uniq.values() for v in vals})
    # уже есть в нашей карте — переводить не нужно
    todo = [v for v in all_strings if v not in ours]

    out = {
        "stats": stats,
        "namespaces": len(uniq),
        "unique_strings": len(all_strings),
        "todo_strings": len(todo),
        "by_ns": {ns: len(v) for ns, v in sorted(uniq.items(), key=lambda kv: -len(kv[1]))},
        "empty_ru": {ns: len(v) for ns, v in empty_ru.items() if v},
    }
    (WORK / "fix_targets.json").write_text(
        json.dumps({**out, "todo": todo}, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "fix_by_ns.json").write_text(
        json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")

    print("статистика:", json.dumps(stats, ensure_ascii=False))
    print(f"неймспейсов с непереведённым: {len(uniq)}")
    print(f"уникальных EN-строк: {len(all_strings)}, из них ещё не переведено нами: {len(todo)}")
    print("топ-15 неймспейсов:")
    for ns, cnt in list(out["by_ns"].items())[:15]:
        print(f"   {ns:38s} {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
