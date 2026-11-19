"""Восстановление кэша переводов книг (work/cache_deepseek_books.json).

Ситуация: датапак-jar в mods/ собран из полного набора переводов страниц,
а work/cache_deepseek_books.json оказался урезанным (6 записей из 40).
При пересборке датапака часть страниц осталась на английском.

Восстанавливаем кэш, сопоставляя страницы оригинала (из модов) и перевода
(из собранного датапак-jar): порядок страниц в лут-таблице сохраняется.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = HERE / "work"
MODS = ROOT / "mods"
JAR = ROOT / "mods" / "zz_linggango_ru_books.jar"
CACHE = WORK / "cache_deepseek_books.json"


def page_texts(node, out: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("function") in ("minecraft:set_written_book_pages",
                                   "minecraft:set_book_contents"):
            pages = node.get("pages") or node.get("value") or []
            if isinstance(pages, str):
                pages = [pages]
            for pg in pages:
                raw = pg.get("raw") if isinstance(pg, dict) else pg
                if isinstance(raw, str) and raw:
                    out.append(raw)
        for v in node.values():
            page_texts(v, out)
    elif isinstance(node, list):
        for v in node:
            page_texts(v, out)


def main() -> None:
    pages = json.loads((WORK / "book_pages.json").read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    with zipfile.ZipFile(JAR) as z:
        names = set(z.namelist())
        for key in pages:
            jar, path = key.split("|", 1)
            if path not in names:
                print(f"  {path}: нет в jar — пропуск")
                continue
            with zipfile.ZipFile(MODS / jar) as zm:
                en_doc = json.loads(zm.read(path).decode("utf-8"))
            ru_doc = json.loads(z.read(path).decode("utf-8"))
            en: list[str] = []
            ru: list[str] = []
            page_texts(en_doc, en)
            page_texts(ru_doc, ru)
            if len(en) != len(ru):
                print(f"  {path}: страниц в оригинале {len(en)}, в jar {len(ru)} — пропуск")
                continue
            added = 0
            for e, r in zip(en, ru):
                if e != r and e not in cache:
                    cache[e] = r
                    added += 1
            print(f"  {path}: страниц {len(en)}, добавлено в кэш {added}")

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nкэш: {len(cache)} записей → {CACHE}")

    missing = [t for texts in pages.values() for t in texts if t not in cache]
    print(f"страниц без перевода в кэше: {len(missing)}")


if __name__ == "__main__":
    main()
