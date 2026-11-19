"""Проверка собранного ресурспака Linggango.

Проверяет:
  1. Ни один перевод мода не потерян (в Minecraft файл языка ресурспака заменяет
     файл мода целиком — если пишеть свой ru_ru.json без слияния, чужие
     переводы пропадают).
  2. Сколько ключей в игре остаются на английском (ru == en или ключ отсутствует).
  3. Какие пространства имён и моды дают больше всего английского текста.

Запуск:
    python3 verify_pack.py            # по pack_build/
    python3 verify_pack.py --zip      # по готовому zip
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = INSTANCE
MODS = ROOT / "mods"
CYR = re.compile(r"[а-яёА-ЯЁ]")


def load_json_bytes(b: bytes):
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:
        return None


def collect_mods() -> tuple[dict, dict]:
    en_by_ns: dict[str, dict] = collections.defaultdict(dict)
    ru_by_ns: dict[str, dict] = collections.defaultdict(dict)
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
            data = load_json_bytes(z.read(name))
            if not isinstance(data, dict):
                continue
            ns = folder.split("/")[1]
            (en_by_ns if fname == "en_us.json" else ru_by_ns)[ns].update(data)
    return en_by_ns, ru_by_ns


def collect_pack(folder: pathlib.Path | None, zip_path: pathlib.Path | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if folder and folder.exists():
        for p in folder.glob("assets/*/lang/ru_ru.json"):
            ns = p.parts[-3]
            data = load_json_bytes(p.read_bytes())
            if isinstance(data, dict):
                out[ns] = data
    elif zip_path and zip_path.exists():
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                if name.startswith("assets/") and name.endswith("/lang/ru_ru.json"):
                    ns = name.split("/")[1]
                    data = load_json_bytes(z.read(name))
                    if isinstance(data, dict):
                        out[ns] = data
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", action="store_true", help="проверять готовый zip, а не pack_build")
    args = ap.parse_args()

    en_by_ns, ru_by_ns = collect_mods()
    pack = collect_pack(None if args.zip else HERE / "pack_build",
                        ROOT / "resourcepacks" / "zz_linggango_ru.zip" if args.zip else None)

    lost_total = 0
    english = 0
    english_by_ns: collections.Counter = collections.Counter()
    mod_by_ns: dict[str, str] = {}

    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "/lang/en_us.json" not in name:
                continue
            ns = name.rsplit("/", 1)[0].split("/")[1]
            mod_by_ns.setdefault(ns, jar.stem)

    for ns, en in en_by_ns.items():
        mod_ru = ru_by_ns.get(ns, {})
        pack_ru = pack.get(ns)
        # итоговый файл в игре: файл ресурспака заменяет файл мода целиком.
        # Если своего файла у пака нет — в игре остаётся файл мода.
        if pack_ru is None:
            effective = dict(mod_ru)
        else:
            effective = dict(pack_ru)
            # 1. потерянные переводы мода
            for key in mod_ru:
                if key not in effective:
                    lost_total += 1
        # 2. английский текст в игре
        for key, val in en.items():
            if not isinstance(val, str) or not val.strip():
                continue
            cur = effective.get(key)
            if cur is None or cur == val:
                english += 1
                english_by_ns[ns] += 1

    print(f"пространств имён в модах: {len(en_by_ns)}")
    print(f"файлов ru_ru в паке: {len(pack)}")
    print(f"ПОТЕРЯНО переводов мода: {lost_total}")
    print(f"ключей осталось на английском: {english}")
    print("\nтоп-15 пространств по английскому тексту:")
    for ns, cnt in english_by_ns.most_common(15):
        print(f"  {ns:32s} {cnt:5d}   ({mod_by_ns.get(ns, '?')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
