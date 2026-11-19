"""Перевод непереведённых текстов в книгах Patchouli (work/patchouli_ru.json).

Сборщик ресурспака переводит поля text/title/description/... в книгах через
карту work/patchouli_ru.json (EN → RU). Строки, которых в карте нет, остаются
английскими. Этот скрипт собирает такие строки из en_us-книг модов и
переводит их через DeepSeek V4.1 Flash.

Запуск:
    python3 fix_patchouli.py                 # показать выборку
    python3 fix_patchouli.py --limit 40      # тест на первых строках
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODS = ROOT / "mods"
WORK = HERE / "work"
PO_RU = WORK / "patchouli_ru.json"

sys.path.insert(0, str(HERE))
from brands import restore_brands  # noqa: E402
from tr_engine import Protector  # noqa: E402

TEXT_FIELDS = ("text", "title", "description", "subtitle", "header", "footer", "name")
CYR = re.compile(r"[а-яёА-ЯЁ]")
WORD = re.compile(r"[A-Za-zА-Яа-я]{3,}")
FILEY = re.compile(r"\.(png|jpg|jpeg|gif|json|snbt)$", re.I)


def collect_en_books() -> dict[str, list[str]]:
    """ns -> список английских строк из полей книг, которые вообще можно перевести."""
    out: dict[str, list[str]] = {}
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "patchouli_books" not in name or not name.endswith(".json"):
                continue
            parts = name.split("/")
            if "en_us" not in parts:
                continue
            try:
                data = json.loads(z.read(name).decode("utf-8"), strict=False)
            except Exception:
                continue
            ns = parts[parts.index("patchouli_books") - 1]

            def walk(node: dict, acc: list[str]) -> None:
                for k, v in node.items():
                    if isinstance(v, str):
                        if k in TEXT_FIELDS:
                            acc.append(v)
                    elif isinstance(v, dict):
                        walk(v, acc)
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                walk(item, acc)

            acc: list[str] = []
            walk(data, acc)
            for v in acc:
                t = v.strip()
                if not t or len(t) < 3:
                    continue
                if FILEY.search(t) or t.startswith("http"):
                    continue
                if not WORD.findall(re.sub(r"\$\([^)]*\)", "", t)):
                    continue
                out.setdefault(ns, [])
                if v not in out[ns]:
                    out[ns].append(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    po = json.loads(PO_RU.read_text(encoding="utf-8")) if PO_RU.exists() else {}
    books = collect_en_books()
    all_vals = sorted({v for vals in books.values() for v in vals})
    todo = [v for v in all_vals if v not in po or po.get(v) == v]
    print(f"строк в книгах: {len(all_vals)}, ещё не переведено: {len(todo)}")
    if args.limit:
        todo = todo[:args.limit]
    if args.dry_run:
        for v in todo[:20]:
            print("   ", repr(v[:90]))
        return 0
    if not todo:
        print("нечего переводить")
        return 0

    from deepseek_backend import DeepSeekBackend
    from fix_translate import Hints, looks_like_name

    glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))
    mods_ru = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    prot = Protector(glossary, mode="none", keep_spaces=True)
    hints = Hints(glossary, {**mods_ru, **po})
    backend = DeepSeekBackend()

    masked = {s: prot.protect(s) for s in todo}
    chunks = [todo[i:i + args.batch] for i in range(0, len(todo), args.batch)]
    ok: dict[str, str] = {}
    bad: list[tuple[str, str, str]] = []
    done = [0]

    def do_chunk(chunk: list[str]):
        payload = [{"en": masked[s][0], "terms": hints.for_string(s)} for s in chunk]
        try:
            out = backend.translate_batch_hinted(payload)
        except Exception as exc:  # noqa: BLE001
            return [(s, "", f"ошибка: {exc}") for s in chunk]
        res = []
        for s, ru in zip(chunk, out):
            full = restore_brands(s, prot.restore(ru, masked[s][1]))
            if not full.strip():
                res.append((s, full, "пусто"))
            elif not CYR.search(full) and WORD.findall(re.sub(r"\$\([^)]*\)", "", s)):
                if looks_like_name(s):
                    res.append((s, full, None))   # имя собственное — оставляем как есть
                else:
                    res.append((s, full, "нет кириллицы"))
            elif "[" in full and re.search(r"\[\d+\]", full):
                res.append((s, full, "остались токены"))
            else:
                res.append((s, full, None))
        return res

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for res in pool.map(do_chunk, chunks):
            for s, ru, reason in res:
                if reason:
                    bad.append((s, ru, reason))
                else:
                    ok[s] = ru
            done[0] += 1
            if done[0] % 5 == 0 or done[0] == len(chunks):
                print(f"[{done[0]}/{len(chunks)}] готово: {len(ok)}, отбраковано: {len(bad)}, "
                      f"{time.time() - t0:.0f}s", flush=True)

    po.update(ok)
    PO_RU.write_text(json.dumps(po, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "patchouli_rejected.json").write_text(
        json.dumps([{"en": a, "ru": b, "why": c} for a, b, c in bad], ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\nпереведено: {len(ok)}, отбраковано: {len(bad)} → work/patchouli_rejected.json")
    for a, b, c in bad[:10]:
        print(f"   [{c}] {a[:70]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
