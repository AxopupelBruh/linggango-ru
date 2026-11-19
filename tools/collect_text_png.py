"""Собирает в /home/ax/Pictures/a все PNG, на которых распознан английский текст.

Pipeline:
  1) обход mods/*.jar, resourcepacks/*.zip и собственных папок инстанса;
  2) дешёвый отбор (путь-маркер + геометрия «широкое и низкое»);
  3) tesseract (eng, psm 11) по каждому кандидату — 12 процессов;
  4) в результат идут картинки, где найдено слово из 3+ латинских букв;
  5) рядом: index.html (галерея), manifest.csv, contact-*.png (контактные листы).
"""
from __future__ import annotations

import csv
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path("/home/ax/Documents/curseforge/minecraft/Instances/Linggango")
WORK = ROOT / ".linggango-translate" / "work"
OUT = Path("/home/ax/Pictures/a")
TMP = Path("/home/ax/Pictures/.pngscan_tmp")

KEYWORDS = [
    "sign", "gui", "tooltip", "info", "panel", "book", "quest", "label",
    "banner", "button", "screen", "title", "description", "hint", "lore",
    "card", "poster", "journal", "letter", "scroll", "newspaper", "tab",
    "header", "footer", "overlay", "dialog", "note", "cover", "page",
    "recipe", "schematic", "diagram", "alert", "popup", "holo", "logo",
    "caption", "readme", "credits", "changelog", "badge", "emblem",
]

SKIP = re.compile(
    r"/textures/(blocks|items|mobs|entity|models|particle|armor|trims|bed|"
    r"door|boat|chest|painting|colours|fluid|ore|glass|water)/"
    r"|/models/|/particle/|_e\.png$", re.I)

WORD = re.compile(r"[A-Za-z]{3,}")
USED_FLAT: set[str] = set()


def geometric(img: Image.Image) -> bool:
    w, h = img.size
    if h > 512 or h < 10 or w < 96:
        return False
    return w / max(1, h) >= 1.8


def real_text(words: str) -> bool:
    """Tesseract часто галлюцинирует на картинках без текста ("mLE", "OORS magAwS").

    Оставляем только распознанный текст, где есть минимум ДВА слова по 4+ буквы
    с гласной — так отсеивается мусор, а реальные надписи проходят.
    """
    good = [w for w in WORD.findall(words) if len(w) >= 4 and re.search(r"[aeiouyAEIOUY]", w)]
    return len(good) >= 2

def ocr_one(job: tuple[str, str, bytes]) -> tuple[str, str, str, str]:
    """(src, path, data) -> (src, path, размер, распознанный текст)."""
    src, path, data = job
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        out = subprocess.run(
            ["tesseract", tmp, "stdout", "-l", "eng", "--psm", "11"],
            capture_output=True, text=True, timeout=30).stdout
    except Exception:
        out = ""
    finally:
        os.unlink(tmp)
    words = WORD.findall(out)
    return src, path, out.strip(), " ".join(words)


def gather() -> list[tuple[str, str, bytes]]:
    jobs: list[tuple[str, str, bytes]] = []
    archives = [(p.name, p) for p in sorted(ROOT.glob("mods/*.jar"))]
    archives += [(p.name, p) for p in sorted(ROOT.glob("resourcepacks/*.zip"))]
    for src_name, path in archives:
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            continue
        for name in z.namelist():
            if not name.lower().endswith(".png"):
                continue
            low = name.lower()
            if SKIP.search(low):
                continue
            base = os.path.basename(low)
            if base in ("logo.png", "pack.png", "favicon.png", "icon.png"):
                continue
            try:
                data = z.read(name)
                img = Image.open(BytesIO(data))
                w, h = img.size
            except Exception:
                continue
            if min(w, h) < 16:
                continue
            if not (any(k in low for k in KEYWORDS) or geometric(img)):
                continue
            jobs.append((src_name, name, data))

    # собственные папки инстанса (ассеты пака, квесты, миры)
    for base in []:
        folder = ROOT / base
        if not folder.exists():
            continue
        for p in folder.rglob("*.png"):
            try:
                data = p.read_bytes()
                img = Image.open(BytesIO(data))
                w, h = img.size
            except Exception:
                continue
            if min(w, h) < 16:
                continue
            jobs.append((f"instance/{base}", str(p.relative_to(ROOT)), data))
    return jobs


def main() -> int:
    USED_FLAT.clear()
    jobs = gather()
    print(f"кандидатов на OCR: {len(jobs)}", flush=True)
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)

    hits = []
    with ProcessPoolExecutor(max_workers=12) as ex:
        for i, (src, path, text, words) in enumerate(ex.map(ocr_one, jobs, chunksize=8)):
            if words:   # фильтр мусора делает build_png_gallery.py (словарь + слова из lang-файлов)
                hits.append((src, path, text, words))
            if (i + 1) % 1000 == 0:
                print(f"  OCR {i + 1}/{len(jobs)}, найдено {len(hits)}", flush=True)
    print(f"с текстом: {len(hits)}", flush=True)
    import json
    json.dump([{"src": a, "path": b, "text": c, "words": d} for a, b, c, d in hits],
              open(WORK / "ocr_hits.json", "w"), ensure_ascii=False)

    OUT.mkdir(parents=True, exist_ok=True)
    img_dir = OUT / "images"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True)

    rows = []
    for src, path, text, words in hits:
        flat = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{Path(src).stem}__{path}")[-140:]
        if flat in USED_FLAT:
            base, ext = os.path.splitext(flat)
            k = 2
            while f"{base}_{k}{ext}" in USED_FLAT:
                k += 1
            flat = f"{base}_{k}{ext}"
        USED_FLAT.add(flat)
        out_rel = f"images/{flat}"
        # достаём файл из архива
        if src.startswith("instance/"):
            src_path = ROOT / path
            try:
                shutil.copy2(src_path, OUT / out_rel)
            except Exception:
                continue
        else:
            for p in ROOT.glob("mods/*.jar"):
                if p.name != src:
                    continue
                with zipfile.ZipFile(p) as z:
                    (OUT / out_rel).write_bytes(z.read(path))
                break
            else:
                for p in ROOT.glob("resourcepacks/*.zip"):
                    if p.name != src:
                        continue
                    with zipfile.ZipFile(p) as z:
                        (OUT / out_rel).write_bytes(z.read(path))
                    break
        try:
            w, h = Image.open(OUT / out_rel).size
        except Exception:
            continue
        rows.append({"out": out_rel, "src": src, "path": path, "w": w, "h": h,
                     "text": " ".join(words.split())[:300]})

    with (OUT / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["file", "source_archive", "source_path", "width", "height", "ocr_text"])
        for r in rows:
            wr.writerow([r["out"], r["src"], r["path"], r["w"], r["h"], r["text"]])

    # галерея
    cards = []
    for r in sorted(rows, key=lambda x: (x["src"], x["path"])):
        cards.append(f"""<figure>
<img src="{html.escape(r['out'])}" loading="lazy">
<figcaption><b>{html.escape(Path(r['src']).stem)}</b><br><span class=p>{html.escape(r['path'])}</span><br><span class=t>{html.escape(r['text'][:160])}</span></figcaption>
</figure>""")
    (OUT / "index.html").write_text(f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>PNG с английским текстом — Linggango</title>
<style>
body{{background:#1b1b1f;color:#e8e8ea;font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 6px}}
p.note{{color:#9aa0a6;margin:0 0 20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
figure{{margin:0;background:#24242a;border:1px solid #34343c;border-radius:8px;padding:10px}}
img{{max-width:100%;max-height:220px;object-fit:contain;background:
 repeating-conic-gradient(#333 0 25%, #2a2a30 0 50%) 50%/16px 16px;border-radius:4px;display:block;margin-bottom:8px}}
figcaption{{font-size:12px;word-break:break-word}}
.p{{color:#8ab4f8}}
.t{{color:#9aa0a6}}
</style></head><body>
<h1>PNG с английским текстом — {len(rows)} шт.</h1>
<p class="note">Распознано tesseract (eng). Отсортировано по архиву. Источник: mods/*.jar, resourcepacks/*.zip и папки инстанса.</p>
<div class="grid">
{''.join(cards)}
</div></body></html>""", encoding="utf-8")
    print(f"готово: {len(rows)} файлов → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
