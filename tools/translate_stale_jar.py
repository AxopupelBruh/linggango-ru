#!/usr/bin/env python3
"""Свежий перевод строк, где чужой ru_ru.json в jar отстал от en_us.json.

Причина дефекта: мод кладёт в jar свой перевод от прошлой версии. Сборщик
(правило «чужой перевод не трогаем») брал его как есть, и в игре появлялись
чужие числа и смысл: «Deals 25%» -> «Возвращает 35%», «Y level -32 and 64»
-> «на уровне Y 50 и ниже», тултипы, съехавшие на соседний ключ.

Логика:
  1) по всем jar собираем en_us.json и ru_ru.json;
  2) берём ключи, где чужой перевод есть, но набор чисел в нём не совпадает
     с en_us (с нормализацией «6» == «шести» и «2,000» == «2000»);
  3) если для английского текста уже есть наш перевод с верными числами —
     используем его, модель не зовём;
  4) остальное переводим через DeepSeek и кладём в work/stale_fix_ru.json.

Сборщик (build_resourcepack.py) применяет этот файл последним: сначала
свой/чужой перевод, потом наши правки по тексту, потом work/stale_fix_ru.json.

Запуск:
    python3 translate_stale_jar.py            # перевести недостающее
    python3 translate_stale_jar.py --dry-run  # только показать объём
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import INSTANCE  # noqa: E402

HERE = Path(__file__).resolve().parent
MODS = INSTANCE / "mods"
WORK = HERE / "work"
OUT = WORK / "stale_fix_ru.json"

# Числительные словами: «шестью вагонами» вместо «6 carriages» — не расхождение.
NUMWORDS = {
    "ноль": 0, "один": 1, "одна": 1, "одно": 1, "одну": 1, "одного": 1, "одной": 1,
    "одним": 1, "одном": 1, "два": 2, "две": 2, "двух": 2, "двум": 2, "двумя": 2,
    "три": 3, "трёх": 3, "трех": 3, "трём": 3, "трем": 3, "тремя": 3, "четыре": 4,
    "четырёх": 4, "четырех": 4, "пять": 5, "пяти": 5, "шесть": 6, "шести": 6,
    "шестью": 6, "семь": 7, "семи": 7, "семью": 7, "восемь": 8, "восьми": 8,
    "девять": 9, "девяти": 9, "десять": 10, "десяти": 10, "одиннадцать": 11,
    "двенадцать": 12, "двадцать": 20, "тридцать": 30, "сорок": 40,
    "пятьдесят": 50, "сто": 100, "двести": 200, "тысяча": 1000,
    # английские — иначе «Seven Curses» -> «семью проклятиями» даёт ложное
    # расхождение: в EN числа нет, в RU появилось.
    "zero": 0, "one": 1, "single": 1, "once": 1, "two": 2, "twice": 2,
    "double": 2, "three": 3, "thrice": 3, "triple": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "hundred": 100, "thousand": 1000,
}

# Служебные токены, которые обязаны пережить перевод без изменений.
RE_CODE = re.compile(r"§.")
RE_ARG = re.compile(r"%(?:\d+\$)?[sdif]")
RE_TAG = re.compile(r"</?(?:grad|shadow|wave|typewriter|br|bold|italic|color)[^<>]*>")
RE_ID = re.compile(r"\b[a-z][a-z0-9_]*:[a-z0-9_/]+\b")


def numbers(text: str) -> tuple[str, ...]:
    """Все числа строки: цифрами и словами, в нормальном виде."""
    plain = RE_CODE.sub("", text)
    # 2,000 / 2 000 / 2.000 -> 2000 (разделитель тысяч)
    plain = re.sub(r"(?<=\d)[,\u00a0\u202f ](?=\d{3}\b)", "", plain)
    out = [n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", plain)]
    for word in re.findall(r"[а-яё]+", plain.lower()):
        if word in NUMWORDS:
            out.append(str(NUMWORDS[word]))
    return tuple(sorted(out))


def load_lang(data: bytes) -> dict:
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            obj = json.loads(data.decode(enc))
        except Exception:
            continue
        return obj if isinstance(obj, dict) else {}
    return {}


def collect() -> tuple[dict, dict]:
    """Собирает en_us.json и ru_ru.json по всем модам."""
    en_by_ns: dict[str, dict] = defaultdict(dict)
    ru_by_ns: dict[str, dict] = defaultdict(dict)
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
            ns = folder.split("/")[1]
            (en_by_ns if fname == "en_us.json" else ru_by_ns)[ns].update(
                load_lang(z.read(name)))
    return en_by_ns, ru_by_ns


def find_broken(en_by_ns: dict, ru_by_ns: dict) -> list[tuple[str, str, str, str]]:
    """Ключи, где чужой перевод разошёлся по числам с оригиналом."""
    broken = []
    for ns, en in en_by_ns.items():
        jr = ru_by_ns.get(ns, {})
        for key, val in en.items():
            if not isinstance(val, str) or not val.strip():
                continue
            cur = jr.get(key)
            if not isinstance(cur, str) or not cur.strip() or cur == val:
                continue
            if numbers(cur) == numbers(val):
                continue
            broken.append((ns, key, val, cur))
    return broken


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    en_by_ns, ru_by_ns = collect()
    broken = find_broken(en_by_ns, ru_by_ns)

    ours = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    known = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

    rescue = {}
    need: dict[str, list[str]] = {}
    for ns, key, en_text, bad in broken:
        have = ours.get(en_text)
        if have and have.strip() and numbers(have) == numbers(en_text):
            rescue[en_text] = have
            continue
        if en_text in known:
            continue
        need.setdefault(en_text, []).append(f"{ns}|{key}")

    print(f"съехавших строк: {len(broken)}")
    print(f"  уже переведены нашим словарём: {len(rescue)}")
    print(f"  осталось перевести: {len(need)}")
    if args.dry_run:
        for text, where in list(need.items())[:20]:
            print(f"   {where[0]}\n     {text[:100]!r}")
        return

    lines = list(need)
    if args.limit:
        lines = lines[:args.limit]

    if lines:
        from deepseek_backend import DeepSeekBackend
        import concurrent.futures as cf

        # Провайдер иногда принимает соединение и молчит. Штатный таймаут
        # бэкенда — 300 с, это слишком долго: подменяем на 120 с, чтобы
        # зависшая пачка падала и уходила в повтор, а не вешала весь прогон.
        def make_backend() -> DeepSeekBackend:
            b = DeepSeekBackend()
            orig = b.session.post

            def post(url, **kw):
                kw.setdefault("timeout", 120)
                return orig(url, **kw)

            b.session.post = post
            return b

        step = 10
        chunks = [lines[i:i + step] for i in range(0, len(lines), step)]
        chunks = [c for c in chunks if any(x not in known for x in c)]
        print(f"  пачек: {len(chunks)}", flush=True)

        def do_chunk(chunk: list[str]) -> tuple[list[str], list[str] | None]:
            todo = [x for x in chunk if x not in known]
            if not todo:
                return chunk, []
            b = make_backend()
            for _ in range(2):
                try:
                    return chunk, b.translate_batch(todo)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ошибка пачки ({len(todo)}): {exc}", flush=True)
                    time.sleep(2)
            return chunk, None

        done_count = 0
        with cf.ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(do_chunk, c) for c in chunks]
            for fut in cf.as_completed(futures):
                chunk, res = fut.result()
                done_count += 1
                if not res:
                    continue
                todo = [x for x in chunk if x not in known]
                for src, tr in zip(todo, res):
                    if tr and tr.strip() and tr != src:
                        known[src] = tr
                OUT.write_text(
                    json.dumps(known, ensure_ascii=False, indent=1, sort_keys=True),
                    encoding="utf-8")
                print(f"  пачка {done_count}/{len(chunks)}: всего {len(known)}", flush=True)

    known.update(rescue)
    OUT.write_text(json.dumps(known, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")
    print(f"записано в {OUT}: {len(known)} записей")


if __name__ == "__main__":
    main()
