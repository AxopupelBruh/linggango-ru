"""Аудит: какие символы в переводах не имеют глифа в ванильном шрифте 1.20.1.

Проверяем все слои, которые видно игроку:
  * ресурспак zz_linggango_ru.zip (lang-файлы);
  * датапак zz_linggango_ru_books (страницы книг);
  * квесты FTB (расшифрованные .snbt);
  * скрипт-переводчик подсказок KubeJS.
"""
from __future__ import annotations

import json
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lgq_crypt import decrypt, is_encrypted  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FONT_JSON = Path("/tmp/pngwork/mcfont/assets/minecraft/font/include/default.json")

INVISIBLE = {"", "‌", "‍", "⁠"}


def coverage() -> set[str]:
    cov: set[str] = set()
    d = json.loads(FONT_JSON.read_text(encoding="utf-8"))
    for p in d["providers"]:
        for row in p.get("chars", []):
            cov |= set(row)
    return cov


def scan_texts() -> dict[str, Counter]:
    found: dict[str, Counter] = defaultdict(Counter)
    where: dict[tuple[str, str], str] = {}

    def feed(loc: str, text: str) -> None:
        for ch in text:
            if ch in "\n\r\t":
                continue
            found[loc][ch] += 1
            where.setdefault((loc, ch), text[:110])

    zp = ROOT / "resourcepacks/zz_linggango_ru.zip"
    if zp.exists():
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                if not n.endswith(".json") or "/lang/" not in n:
                    continue
                try:
                    d = json.loads(z.read(n).decode("utf-8"))
                except Exception:
                    continue
                if not isinstance(d, dict):
                    continue
                for k, v in d.items():
                    if isinstance(v, str):
                        feed(f"pack:{n}", v)

    for dp in [ROOT / "datapacks/zz_linggango_ru_books"]:
        if dp.exists():
            for f in dp.rglob("*.json"):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if isinstance(d, dict):
                    for v in d.values():
                        if isinstance(v, str):
                            feed(f"datapack:{f.relative_to(ROOT)}", v)
                        elif isinstance(v, list):
                            for it in v:
                                if isinstance(it, str):
                                    feed(f"datapack:{f.relative_to(ROOT)}", it)

    qroot = ROOT / "config/ftbquests/quests"
    for p in sorted(qroot.rglob("*.snbt")):
        raw = p.read_text(encoding="utf-8", errors="replace")
        t = decrypt(raw) if is_encrypted(raw) else raw
        feed(f"quests:{p.relative_to(qroot)}", t)

    js = ROOT / "kubejs/client_scripts/ru_tooltip_translator.js"
    if js.exists():
        feed("kubejs", js.read_text(encoding="utf-8"))

    return found, where


def main() -> None:
    cov = coverage()
    found, where = scan_texts()
    bad = Counter()
    for loc, c in found.items():
        for ch, n in c.items():
            if ch not in cov:
                bad[ch] += n
    print(f"ванильный шрифт покрывает {len(cov)} символов")
    print(f"НЕ покрыто: {len(bad)} различных символов\n")
    for ch, n in bad.most_common():
        locs = [loc for (loc, c) in where if c == ch][:4]
        try:
            nm = unicodedata.name(ch)
        except ValueError:
            nm = "?"
        flag = " (невидимый)" if ch in INVISIBLE else ""
        print(f"  {ch!r} U+{ord(ch):04X} {nm[:38]:40s} ×{n:<5d}{flag}")
        print(f"      {locs}")
    print("\nИТОГО непокрытых вхождений:", sum(bad.values()))


if __name__ == "__main__":
    main()
