"""Собирает в /home/ax/Pictures/a/quests все PNG, связанные с квестами.

Источники:
  1) kubejs/assets/customtextures/**  — собственная графика пака (заголовки актов,
     логотипы модов, портреты боссов) — именно её показывают главы FTB Quests;
  2) PNG, на которые прямо ссылаются главы квестов (image: "namespace:path.png").

По каждому файлу прогоняется tesseract; в отчёт попадает распознанный текст.
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
from pathlib import Path

from PIL import Image

ROOT = Path("/home/ax/Documents/curseforge/minecraft/Instances/Linggango")
OUT = Path("/home/ax/Pictures/a/quests")
WORD = re.compile(r"[A-Za-z]{3,}")


def ocr_one(job):
    name, data = job
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        out = subprocess.run(["tesseract", tmp, "stdout", "-l", "eng", "--psm", "11"],
                             capture_output=True, text=True, timeout=40).stdout
    except Exception:
        out = ""
    finally:
        os.unlink(tmp)
    return name, " ".join(WORD.findall(out)), out.strip()


def quest_refs() -> set[str]:
    sys.path.insert(0, str(ROOT / ".linggango-translate"))
    from lgq_crypt import decrypt_file, is_encrypted
    refs = set()
    for f in sorted((ROOT / "config/ftbquests/quests").rglob("*.snbt")):
        raw = f.read_text(encoding="utf-8", errors="replace")
        if is_encrypted(raw.strip()):
            raw = decrypt_file(f)
        for m in re.finditer(r'image:\s*"([a-z0-9_.-]+):([^\"]+\.png)"', raw):
            refs.add(f"{m.group(1)}:{m.group(2)}")
    return refs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    jobs: list[tuple[str, bytes]] = []
    used: set[str] = set()

    # 1) собственная графика пака
    base_dir = ROOT / "kubejs/assets/customtextures"
    for p in sorted(base_dir.rglob("*.png")):
        rel = p.relative_to(base_dir)
        flat = re.sub(r"[^A-Za-z0-9._-]+", "_", str(rel))
        if flat in used:
            flat = f"{len(used)}_{flat}"
        used.add(flat)
        jobs.append((flat, p.read_bytes()))

    # 2) PNG из модов, на которые ссылаются главы
    refs = quest_refs()
    for p in sorted(ROOT.glob("mods/*.jar")):
        try:
            z = zipfile.ZipFile(p)
        except Exception:
            continue
        for name in z.namelist():
            if not name.lower().endswith(".png"):
                continue
            parts = name.split("/")
            if len(parts) < 3 or parts[0] != "assets":
                continue
            ns = parts[1]
            rel = "/".join(parts[2:])
            if f"{ns}:{rel}" not in refs:
                continue
            flat = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p.stem}__{ns}__{rel}")[-130:]
            if flat in used:
                flat = f"{len(used)}_{flat}"
            used.add(flat)
            try:
                jobs.append((flat, z.read(name)))
            except KeyError:
                pass

    print(f"квестовых PNG: {len(jobs)}", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=12) as ex:
        for name, words, text in ex.map(ocr_one, jobs, chunksize=4):
            results.append((name, words, text))

    rows = []
    ocr_by_name = {n: (w, t) for n, w, t in results}
    for name, data in jobs:
        (OUT / name).write_bytes(data)
        try:
            w, h = Image.open(OUT / name).size
        except Exception:
            w = h = 0
        words, text = ocr_by_name.get(name, ("", ""))
        rows.append({"file": name, "w": w, "h": h, "words": words, "text": text})

    with (OUT / "quests_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["file", "width", "height", "ocr_words", "ocr_text"])
        for r in sorted(rows, key=lambda x: x["file"]):
            wr.writerow([r["file"], r["w"], r["h"], r["words"], r["text"][:400]])

    cards = []
    for r in sorted(rows, key=lambda x: (not x["words"], x["file"])):
        badge = ('<span class="badge">ТЕКСТ</span>' if r["words"] else
                 '<span class="badge none">без текста</span>')
        cards.append(
            f'<figure><img src="{html.escape(r["file"])}" loading="lazy">'
            f'<figcaption>{badge}<br><span class="t">{html.escape(r["text"][:200])}</span>'
            f'<br><span class="p">{r["w"]}×{r["h"]}</span></figcaption></figure>')
    (OUT / "index.html").write_text(f"""<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><title>Квестовые PNG — Linggango</title><style>
body{{background:#1b1b1f;color:#e8e8ea;font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 6px}}p.note{{color:#9aa0a6;margin:0 0 18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
figure{{margin:0;background:#24242a;border:1px solid #34343c;border-radius:8px;padding:9px}}
img{{max-width:100%;max-height:200px;object-fit:contain;background:
 repeating-conic-gradient(#333 0 25%,#2a2a30 0 50%) 50%/16px 16px;border-radius:4px;display:block;margin-bottom:7px}}
figcaption{{font-size:12px;word-break:break-word}}
.badge{{background:#7a4a1e;color:#ffd9a8;padding:1px 6px;border-radius:4px;font-size:11px}}
.badge.none{{background:#33363d;color:#9aa0a6}}
.t{{color:#c8c8d0}}.p{{color:#8ab4f8}}
</style></head><body>
<h1>Квестовые PNG — {len(rows)} шт.</h1>
<p class="note">Собственная графика пака (kubejs/assets/customtextures) + PNG из модов, на которые ссылаются главы.
Отсортировано: сначала картинки с распознанным английским текстом.</p>
<div class="grid">{''.join(cards)}</div></body></html>""", encoding="utf-8")

    txt = sum(1 for r in rows if r["words"])
    print(f"скопировано: {len(rows)} | с английским текстом: {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
