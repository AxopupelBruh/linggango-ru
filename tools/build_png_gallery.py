"""Финальный шаг: фильтрует OCR-хиты, раскладывает файлы и собирает галерею.

Фильтр отсекает мусор tesseract'а: оставляем картинки, где распознано
- минимум 2 слова по 4+ буквы с гласной, ИЛИ
- хотя бы одно слово из словаря английских слов, собранного из lang-файлов модов.
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path("/home/ax/Documents/curseforge/minecraft/Instances/Linggango")
WORK = ROOT / ".linggango-translate" / "work"
OUT = Path("/home/ax/Pictures/a")
WORD = re.compile(r"[A-Za-z]{3,}")
USED: set[str] = set()

VOCAB = set(json.loads((WORK / "en_vocab.json").read_text(encoding="utf-8")))


def good_words(words: str) -> list[str]:
    return [w for w in WORD.findall(words)
            if len(w) >= 4 and re.search(r"[aeiouyAEIOUY]", w)]


def keep(words: str) -> bool:
    gw = good_words(words)
    if len(gw) >= 2:
        return True
    return any(w.lower() in VOCAB for w in WORD.findall(words))


def unique_flat(src: str, path: str) -> str:
    flat = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{Path(src).stem}__{path}")[-140:]
    if flat in USED:
        base, ext = os.path.splitext(flat)
        k = 2
        while f"{base}_{k}{ext}" in USED:
            k += 1
        flat = f"{base}_{k}{ext}"
    USED.add(flat)
    return flat


def extract(src: str, path: str, dest: Path) -> bool:
    try:
        if src.startswith("instance/"):
            shutil.copy2(ROOT / path, dest)
            return True
        for folder in ("mods", "resourcepacks"):
            for p in (ROOT / folder).glob("*"):
                if p.name != src:
                    continue
                try:
                    z = zipfile.ZipFile(p)
                except Exception:
                    return False
                try:
                    dest.write_bytes(z.read(path))
                    return True
                except KeyError:
                    return False
        return False
    except Exception:
        return False


def main() -> int:
    hits = json.loads((WORK / "ocr_hits.json").read_text(encoding="utf-8"))
    print("OCR-хитов всего:", len(hits))
    good = [h for h in hits if keep(h["words"])]
    print("после фильтра мусора:", len(good))

    OUT.mkdir(parents=True, exist_ok=True)
    img_dir = OUT / "images"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True)

    rows = []
    for h in good:
        flat = unique_flat(h["src"], h["path"])
        out_rel = f"images/{flat}"
        if not extract(h["src"], h["path"], OUT / out_rel):
            continue
        try:
            w, hgt = Image.open(OUT / out_rel).size
        except Exception:
            continue
        rows.append({"out": out_rel, "src": h["src"], "path": h["path"],
                     "w": w, "h": hgt, "text": " ".join(h["words"].split())[:300]})

    with (OUT / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["file", "source_archive", "source_path", "width", "height", "ocr_text"])
        for r in rows:
            wr.writerow([r["out"], r["src"], r["path"], r["w"], r["h"], r["text"]])

    cards = []
    for r in sorted(rows, key=lambda x: (x["src"], x["path"])):
        cards.append(
            f'<figure><img src="{html.escape(r["out"])}" loading="lazy">'
            f'<figcaption><b>{html.escape(Path(r["src"]).stem)}</b><br>'
            f'<span class="p">{html.escape(r["path"])}</span><br>'
            f'<span class="t">{html.escape(r["text"][:170])}</span></figcaption></figure>')
    (OUT / "index.html").write_text(f"""<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><title>PNG с английским текстом — Linggango</title>
<style>
body{{background:#1b1b1f;color:#e8e8ea;font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 6px}}
p.note{{color:#9aa0a6;margin:0 0 20px;max-width:900px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
figure{{margin:0;background:#24242a;border:1px solid #34343c;border-radius:8px;padding:10px}}
img{{max-width:100%;max-height:240px;object-fit:contain;background:
 repeating-conic-gradient(#333 0 25%, #2a2a30 0 50%) 50%/16px 16px;border-radius:4px;display:block;margin-bottom:8px}}
figcaption{{font-size:12px;word-break:break-word}}
.p{{color:#8ab4f8}}.t{{color:#9aa0a6}}
</style></head><body>
<h1>PNG с английским текстом — {len(rows)} шт.</h1>
<p class="note">Отобраны tesseract'ом (eng) из mods/*.jar, resourcepacks/*.zip и папок инстанса;
мусор распознавания отфильтрован. Файл → <code>images/</code>, источник — в подписи под картинкой.
Полный список — в <a href="manifest.csv">manifest.csv</a>.</p>
<div class="grid">{''.join(cards)}</div></body></html>""", encoding="utf-8")

    print(f"скопировано: {len(rows)}")
    for k, v in Counter(r["src"] for r in rows).most_common(12):
        print(f"   {k[:46]:48s} {v}")

    # контактные листы по архивам
    sheets = OUT / "sheets"
    if sheets.exists():
        shutil.rmtree(sheets)
    sheets.mkdir()
    by_src: dict[str, list[str]] = {}
    for r in rows:
        by_src.setdefault(r["src"], []).append(str(OUT / r["out"]))
    made = 0
    for src, files in by_src.items():
        if len(files) < 3:
            continue
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(src).stem)[:50]
        out = sheets / f"{name}.png"
        try:
            subprocess.run(["montage", *files[:120], "-tile", "6x", "-geometry",
                            "300x300+6+6", "-background", "#1b1b1f", "-fill", "white",
                            "-pointsize", "14", "-label", "%f", str(out)],
                           capture_output=True, timeout=300)
            if out.exists():
                made += 1
        except Exception:
            pass
    print(f"контактных листов: {made} → {sheets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
