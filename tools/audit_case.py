"""Аудит регистра и брендов в текущем переводе Linggango.

Находит:
  * переводы, которые начинаются с маленькой буквы, хотя оригинал — с большой
    (или наоборот: оригинал с маленькой, перевод с большой);
  * переводы, где кириллическая транслитерация бренда (ФТБ, ДЖЭИ, РЕЙ...);
  * переводы, полностью совпадающие с оригиналом (кроме служебных).

Результат: work/case_issues.json = список {ns, key, en, ru, kind}.
"""

from __future__ import annotations

import json
import re
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
from brands import BRAND_RU, restore_brands  # noqa: E402
from lang_json import load_lang_json  # noqa: E402

# транслитерации брендов, которые надо вернуть в английский
BRAND_BAD = re.compile("|".join(re.escape(v) for vs in BRAND_RU.values() for v in vs))
BRAND_FIX = {a: b for b, vs in BRAND_RU.items() for a in vs}

# ведущая разметка (§-коды, теги, пробелы) — её пропускаем, сравнивая первые буквы
LEAD = re.compile(r"^(\s*(?:[§&][0-9a-fk-orA-FK-OR]|\[[^\]]{0,40}\]|<[^>]{0,40}>)*)")
FIRST = re.compile(r"[^\W\d_]", re.UNICODE)


def first_letter(s: str) -> str:
    """Первая буква слова, без учёта ведущих кодов цвета и разметки."""
    m = LEAD.match(s)
    rest = s[m.end():] if m else s
    fm = FIRST.search(rest)
    return fm.group(0) if fm else ""


def main() -> int:
    en: dict[str, dict[str, str]] = defaultdict(dict)
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "/lang/" not in name:
                continue
            folder, fname = name.rsplit("/", 1)
            if fname != "en_us.json":
                continue
            try:
                data = load_lang_json(z.read(name))
            except Exception:
                continue
            en[folder.split("/")[1]].update(data)

    issues: list[dict] = []
    counts = defaultdict(int)
    for p in sorted((HERE / "pack_build").glob("assets/*/lang/ru_ru.json")):
        ns = p.parts[-3]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key, ru in data.items():
            if not isinstance(ru, str):
                continue
            e = en.get(ns, {}).get(key)
            if e is None:
                continue
            if BRAND_BAD.search(ru):
                # чиним только если в оригинале бренд был латиницей
                fixed = restore_brands(e, ru)
                if fixed != ru:
                    issues.append({"ns": ns, "key": key, "en": e, "ru": ru,
                                   "kind": "brand", "fixed": fixed})
                    counts["brand"] += 1
                    continue
            if ru.strip() == e.strip():
                issues.append({"ns": ns, "key": key, "en": e, "ru": ru, "kind": "same"})
                counts["same"] += 1
                continue
            fe, fr = first_letter(e), first_letter(ru)
            if not fe or not fr:
                continue
            if fe.isupper() and fr.islower():
                issues.append({"ns": ns, "key": key, "en": e, "ru": ru,
                               "kind": "lower_start"})
                counts["lower_start"] += 1
            elif fr.isupper() and fe.islower():
                issues.append({"ns": ns, "key": key, "en": e, "ru": ru,
                               "kind": "upper_start"})
                counts["upper_start"] += 1

    (WORK / "case_issues.json").write_text(
        json.dumps(issues, ensure_ascii=False, indent=1), encoding="utf-8")
    print("всего замечаний:", len(issues))
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"   {k:14s} {v}")
    for kind in ("lower_start", "upper_start", "brand", "same"):
        sample = [i for i in issues if i["kind"] == kind][:8]
        if not sample:
            continue
        print(f"\n=== {kind} ===")
        for i in sample:
            print(f"  {i['ns']}/{i['key'][:34]:34s} EN={i['en'][:38]!r}")
            print(f"      RU={i['ru'][:50]!r}" + (f"  -> {i['fixed']!r}" if "fixed" in i else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
