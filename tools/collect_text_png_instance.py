"""Второй проход: PNG из собственных папок инстанса (kubejs, config, saves, ...).

В основном проходе они терялись из-за неверной сборки пути. Здесь путь
строится правильно: path уже относителен к корню инстанса.
"""
from __future__ import annotations

import csv
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
from paths import INSTANCE, WORK_DIR  # noqa: E402

from PIL import Image

ROOT = INSTANCE
OUT = Path("/home/ax/Pictures/a")
WORD = re.compile(r"[A-Za-z]{3,}")
KEYWORDS = ["sign", "gui", "tooltip", "info", "panel", "book", "quest", "label",
            "banner", "button", "screen", "title", "description", "hint", "lore",
            "card", "poster", "journal", "letter", "scroll", "newspaper", "tab",
            "header", "footer", "overlay", "dialog", "note", "cover", "page",
            "recipe", "schematic", "diagram", "alert", "popup", "holo", "logo",
            "caption", "readme", "credits", "changelog", "badge", "emblem"]


def ocr_one(job):
    path, data = job
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        out = subprocess.run(["tesseract", tmp, "stdout", "-l", "eng", "--psm", "11"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        out = ""
    finally:
        os.unlink(tmp)
    return path, out.strip(), " ".join(WORD.findall(out))


def main() -> int:
    folders = ["kubejs", "config", "datapacks", "patchouli_books",
               "quests_structures", "saves", "moonlight-global-datapacks",
               "resourcepacks", "defaultconfigs", "local"]
    jobs = []
    for base in folders:
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
            rel = str(p.relative_to(ROOT))
            if not (any(k in rel.lower() for k in KEYWORDS) or
                    (h <= 512 and w >= 96 and w / max(1, h) >= 1.8)):
                continue
            jobs.append((rel, data))
    print(f"кандидатов из папок инстанса: {len(jobs)}", flush=True)

    hits = []
    with ProcessPoolExecutor(max_workers=12) as ex:
        for path, text, words in ex.map(ocr_one, jobs, chunksize=4):
            if words:
                hits.append((path, text, words))
    print(f"с текстом: {len(hits)}", flush=True)

    rows = []
    for path, text, words in hits:
        flat = re.sub(r"[^A-Za-z0-9._-]+", "_", f"instance__{path}")[-140:]
        out_rel = f"images/{flat}"
        try:
            shutil.copy2(ROOT / path, OUT / out_rel)
            w, h = Image.open(OUT / out_rel).size
        except Exception:
            continue
        rows.append({"out": out_rel, "src": "instance", "path": path,
                     "w": w, "h": h, "text": " ".join(words.split())[:300]})

    with (OUT / "manifest_instance.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["file", "source_archive", "source_path", "width", "height", "ocr_text"])
        for r in rows:
            wr.writerow([r["out"], r["src"], r["path"], r["w"], r["h"], r["text"]])
    print(f"скопировано: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
