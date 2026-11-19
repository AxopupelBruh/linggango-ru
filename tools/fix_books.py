"""Перевод книг в модовых данжах и сборка датапака.

Книги в сундуках — это loot-таблицы с функцией minecraft:set_written_book_pages.
Их не покрывает ни ресурспак, ни KubeJS-переводчик: это готовый текст внутри
JSON. Поэтому перекрываем лут-таблицу датапаком.

Что делает:
  1. Достаёт страницы книг из лут-таблиц модов (work/book_pages.json).
  2. Переводит их через DeepSeek (work/book_pages_ru.json).
  3. Собирает датапак: datapacks/zz_linggango_ru_books/ — перекрытые
     лут-таблицы с русскими страницами.

Запуск:
    python3 fix_books.py extract
    python3 fix_books.py translate
    python3 fix_books.py build
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODS = ROOT / "mods"
WORK = HERE / "work"
DATAPACK = ROOT / "datapacks" / "zz_linggango_ru_books"

sys.path.insert(0, str(HERE))
from deepseek_backend import DeepSeekBackend  # noqa: E402

PACK_FORMAT = 15  # 1.20.1

# лут-таблицы, где внутри сидят книги
TARGETS = [
    ("ATi Structures V1.4.7.jar",
     "data/ati_structures/loot_table/chests/library.json"),
    ("irons_spellbooks-1.20.1-3.15.6.jar",
     "data/irons_spellbooks/loot_tables/chests/citadel/citadel_tomes.json"),
]

# арабский текст — это мем (КpongeBob), переводить не надо
ARABIC = re.compile(r"[؀-ۿ]")


def page_texts(node) -> list[str]:
    """Собирает тексты страниц из функции set_written_book_pages."""
    out: list[str] = []
    if isinstance(node, dict):
        if node.get("function") in ("minecraft:set_written_book_pages",
                                    "minecraft:set_book_contents"):
            pages = node.get("pages") or node.get("value") or []
            if isinstance(pages, str):
                pages = [pages]
            for p in pages:
                if isinstance(p, dict):
                    p = p.get("raw") or p.get("text") or ""
                if p:
                    out.append(p)
        for v in node.values():
            out.extend(page_texts(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(page_texts(v))
    return out


def cmd_extract() -> int:
    pages: dict[str, list[str]] = {}
    for jar, path in TARGETS:
        p = MODS / jar
        if not p.exists():
            print(f"нет jar: {jar}")
            continue
        with zipfile.ZipFile(p) as z:
            d = json.loads(z.read(path).decode("utf-8"))
        texts = [t for t in page_texts(d) if t.strip()]
        pages[f"{jar}|{path}"] = texts
        print(f"{jar}: страниц — {len(texts)}")
    (WORK / "book_pages.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in pages.values())
    print(f"всего страниц: {total}")
    return 0


def cmd_translate() -> int:
    pages = json.loads((WORK / "book_pages.json").read_text(encoding="utf-8"))
    cache_path = WORK / "cache_deepseek_books.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    # плоский список уникальных страниц
    uniq: list[str] = []
    for texts in pages.values():
        for t in texts:
            if t not in uniq:
                uniq.append(t)

    todo = [t for t in uniq if t not in cache and not ARABIC.search(t)]
    print(f"страниц уникальных: {len(uniq)}, к переводу: {len(todo)}")

    backend = DeepSeekBackend()
    for i in range(0, len(todo), 6):
        batch = todo[i:i + 6]
        try:
            got = backend.translate_batch_hinted(
                [{"en": t, "terms": {}} for t in batch])
        except Exception as e:  # noqa: BLE001
            print(f"  ! батч {i}: {e}")
            break
        for t, ru in zip(batch, got):
            cache[t] = ru
        if i % 60 < 6:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0),
                                  encoding="utf-8")
            print(f"  ... {i + len(batch)}/{len(todo)}", flush=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"в кэше: {len(cache)}")
    return 0


def replace_pages(node, tr: dict[str, str]) -> int:
    """Заменяет английские страницы русскими по всём дереве."""
    n = 0
    if isinstance(node, dict):
        if node.get("function") in ("minecraft:set_written_book_pages",
                                    "minecraft:set_book_contents"):
            pages = node.get("pages") or node.get("value") or []
            if isinstance(pages, str):
                pages = [pages]
            new = []
            for p in pages:
                if isinstance(p, dict):
                    key = "raw" if "raw" in p else ("text" if "text" in p else None)
                    if key and p.get(key) in tr:
                        p = dict(p)
                        p[key] = tr[p[key]]
                        n += 1
                new.append(p)
            if isinstance(node.get("pages"), list):
                node["pages"] = new
            else:
                node["value"] = new
        for v in node.values():
            n += replace_pages(v, tr)
    elif isinstance(node, list):
        for v in node:
            n += replace_pages(v, tr)
    return n


def cmd_build() -> int:
    pages = json.loads((WORK / "book_pages.json").read_text(encoding="utf-8"))
    cache_path = WORK / "cache_deepseek_books.json"
    tr = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    if DATAPACK.exists():
        shutil.rmtree(DATAPACK)
    (DATAPACK / "data").mkdir(parents=True, exist_ok=True)
    (DATAPACK / "pack.mcmeta").write_text(json.dumps({
        "pack": {"pack_format": PACK_FORMAT, "description": "Linggango RU: книги в данжах"}
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    total = 0
    for key, texts in pages.items():
        jar, path = key.split("|", 1)
        with zipfile.ZipFile(MODS / jar) as z:
            d = json.loads(z.read(path).decode("utf-8"))
        n = replace_pages(d, tr)
        total += n
        out = DATAPACK / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{path}: переведено страниц — {n}")

    # проверка: английских страниц не осталось
    left = 0
    for key, texts in pages.items():
        jar, path = key.split("|", 1)
        out = DATAPACK / path
        d = json.loads(out.read_text(encoding="utf-8"))
        for t in page_texts(d):
            # арабские страницы — намеренно оставлены (мем), пустые — тоже
            if not t.strip() or ARABIC.search(t):
                continue
            if not re.search(r"[\u0430-\u044f\u0401\u0410-\u042f]", t):
                left += 1
    print(f"\nдатапак: {DATAPACK}")
    print(f"переведено страниц: {total}, осталось без перевода: {left}")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "extract"
    if cmd == "extract":
        return cmd_extract()
    if cmd == "translate":
        return cmd_translate()
    if cmd == "build":
        return cmd_build()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
