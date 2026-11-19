"""Переводит новые lang-ключи Punchy 3.0 и вливает переводы в work/mods_ru.json.

Зачем: после обновления сборки до V6.6.6cf мод Punchy обновляется с 2.8c до 3.0
и приносит 324 новых lang-ключа (en_us: 273 -> 597). Файл языка ресурспака
ЗАМЕНЯЕТ файл мода целиком, поэтому без наших переводов эти строки в игре
останутся английскими.

Словарь модов у нас keyed по английскому тексту (en_us -> ru), поэтому
переводим значения, а не ключи.

Обычный запуск (одним процессом):
    python3 translate_punchy3.py --jar /tmp/punchy3.jar

Ускоренный запуск (4 процесса на 4 ключах):
    for i in 0 1 2 3; do python3 translate_punchy3.py --jar /tmp/punchy3.jar \
        --shard $i --shards 4 --key .deepseek_key$((i+1)) & done; wait
    python3 translate_punchy3.py --jar /tmp/punchy3.jar --merge

Ключи:
    --dry-run  — только показать, словарь не трогать
    --force    — перевести заново, игнорируя кэш
    --merge    — слить кэши шардов в словарь (перевод не запускать)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE, WORK_DIR  # noqa: E402
from tr_engine import Translator, load_glossary  # noqa: E402
from deepseek_backend import DeepSeekBackend  # noqa: E402

HERE = Path(__file__).parent
WORK = WORK_DIR
MODS = INSTANCE / "mods"

CYR = re.compile(r"[Ѐ-ӿ]")
LAT = re.compile(r"[A-Za-z]")
CJK = re.compile(r"[　-鿿＀-￯]")
PLACEHOLDER = re.compile(r"%[0-9]*[a-zA-Z]|§[0-9a-fk-orA-FK-OR]|\{[0-9]*\}")


def en_us(jar: Path) -> dict:
    with zipfile.ZipFile(jar) as z:
        return json.loads(z.read("assets/punchy/lang/en_us.json"))


def current_punchy() -> Path:
    jars = sorted(MODS.glob("punchy-*.jar"))
    if not jars:
        raise SystemExit("в инстансе нет punchy-*.jar")
    return jars[0]


def new_values(new_jar: Path, old_jar: Path) -> tuple[dict, list]:
    new, old = en_us(new_jar), en_us(old_jar)
    added = {k: v for k, v in new.items()
             if k not in old and isinstance(v, str) and v.strip()}
    return added, sorted(set(added.values()))


def shard_name(shard: int, shards: int) -> str:
    return f"cache_deepseek_punchy3_s{shard}.json" if shards > 1 else \
        "cache_deepseek_punchy3.json"


def merge_shards(shards: int) -> int:
    """Сливает кэши шардов в work/mods_ru.json, пишет общий отчёт."""
    merged: dict[str, str] = {}
    keys_map: dict[str, str] = {}
    for s in range(shards):
        p = WORK / shard_name(s, shards)
        if p.exists():
            merged.update(json.loads(p.read_text(encoding="utf-8")))
        rp = WORK / f"punchy3_keys_s{s}.json"
        if rp.exists():
            keys_map.update(json.loads(rp.read_text(encoding="utf-8")))
    rows = [{"en": k, "ru": v} for k, v in merged.items()]
    bad = []
    for row in rows:
        src, ru = row["en"], row["ru"]
        reason = None
        if not ru.strip():
            reason = "пусто"
        elif CJK.search(ru):
            reason = "CJK-символы"
        elif LAT.search(src) and len(LAT.findall(src)) >= 3 and not CYR.search(ru):
            reason = "без кириллицы"
        elif sorted(PLACEHOLDER.findall(src)) != sorted(PLACEHOLDER.findall(ru)):
            reason = "потеряны плейсхолдеры"
        if reason:
            row["problem"] = reason
            bad.append(row)
    (WORK / "punchy3_translations.json").write_text(
        json.dumps({"keys": keys_map, "translations": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"слито строк: {len(merged)} | с замечаниями: {len(bad)}")
    for r in bad:
        print(f"   ! {r['problem']}: {r['en'][:60]!r} -> {r['ru'][:60]!r}")

    dict_path = WORK / "mods_ru.json"
    data = json.loads(dict_path.read_text(encoding="utf-8"))
    added_n = 0
    for src, ru in merged.items():
        if src not in data and ru.strip():
            data[src] = ru
            added_n += 1
    dict_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"в словарь добавлено: {added_n} | всего записей: {len(data)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="перевод новых ключей Punchy 3.0")
    ap.add_argument("--jar", required=True, help="путь к punchy-3.0.jar")
    ap.add_argument("--old-jar", default="", help="старый punchy-*.jar (по умолчанию из инстанса)")
    ap.add_argument("--dry-run", action="store_true", help="не вливать в словарь")
    ap.add_argument("--force", action="store_true", help="перевести заново, игнорируя кэш")
    ap.add_argument("--merge", action="store_true", help="только слить кэши шардов в словарь")
    ap.add_argument("--shard", type=int, default=0, help="индекс шарда")
    ap.add_argument("--shards", type=int, default=1, help="число шардов")
    ap.add_argument("--batch", type=int, default=20,
                    help="строк в одном запросе (больше 30 — модель упирается в max_tokens)")
    ap.add_argument("--key", default="", help="файл с ключом DeepSeek (по умолчанию .deepseek_key)")
    args = ap.parse_args()

    if args.merge:
        return merge_shards(args.shards)

    new_jar = Path(args.jar)
    old_jar = Path(args.old_jar) if args.old_jar else current_punchy()
    if not new_jar.exists():
        raise SystemExit(f"нет файла: {new_jar}")

    added, values = new_values(new_jar, old_jar)
    mine = values[args.shard::args.shards]
    print(f"старая версия: {old_jar.name} ({len(en_us(old_jar))} ключей)")
    print(f"новая версия:  {new_jar.name} ({len(en_us(new_jar))} ключей)")
    print(f"новых ключей: {len(added)} | уникальных строк: {len(values)} | "
          f"шард {args.shard + 1}/{args.shards}: {len(mine)} строк")

    glossary = load_glossary()
    key_file = HERE / (args.key or ".deepseek_key")
    backend = DeepSeekBackend(api_key=key_file.read_text(encoding="utf-8").strip()
                               if key_file.exists() else None)
    backend.max_items = args.batch
    cache = WORK / shard_name(args.shard, args.shards)
    if args.force and cache.exists():
        cache.unlink()
    tr = Translator(backend, glossary, cache_path=cache)

    print(f"перевод {len(mine)} строк (бэкенд {backend.model})…", flush=True)
    out = tr.translate_many(mine)
    tr.cache.save()

    (WORK / f"punchy3_keys_s{args.shard}.json").write_text(
        json.dumps(added, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = [{"en": s, "ru": r} for s, r in zip(mine, out)]
    (WORK / f"punchy3_translations_s{args.shard}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    bad = [r for r in rows
           if not r["ru"].strip() or CJK.search(r["ru"])
           or (LAT.search(r["en"]) and len(LAT.findall(r["en"])) >= 3 and not CYR.search(r["ru"]))]
    print(f"шард готов: {len(rows)} строк | с замечаниями: {len(bad)}")
    for r in bad:
        print(f"   ! {r['en'][:60]!r} -> {r['ru'][:60]!r}")

    if args.shards == 1 and not args.dry_run:
        return merge_shards(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
