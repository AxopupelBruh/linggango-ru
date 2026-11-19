"""Перевод английских меток внутри ссылок Patchouli.

В книгах встречаются конструкции вида:
    $(l:bloodmagic:alchemy_array/functional_arrays/arcane_ash)Arcane Ashes.$(/l)
Метка ссылки — отдельный переводимый текст, но она лежит ВНУТРИ уже
переведённого предложения, поэтому обычная карта значений её не покрывает.

Скрипт:
  1. собирает английские метки ссылок из книг (en_us и собранного пака);
  2. переводит их через DeepSeek V4.1 Flash (с подсказками из карт переводов);
  3. сохраняет карту в work/patchouli_labels_ru.json — сборщик подставит её
     при сборке книг.

Запуск:
    python3 fix_patchouli_labels.py
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
LABELS_RU = WORK / "patchouli_labels_ru.json"

sys.path.insert(0, str(HERE))
from brands import restore_brands  # noqa: E402
from tr_engine import Protector  # noqa: E402

# метка ссылки: $(l:ns:path)Метка$(/l) или $(item)Метка$()
LBL_OPEN = r"\$\((?:l|item|entity|t|c|hover|key|lang)(?:[:/][^)]*)?\)"
LBL_CLOSE = r"\$\((?:/l)?\)"
LBL = re.compile(f"({LBL_OPEN})([^$]*?)({LBL_CLOSE})")
CYR = re.compile(r"[а-яёА-ЯЁ]")
WORD = re.compile(r"[A-Za-zА-Яа-я]{3,}")
ID = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./]+$", re.I)
STOP = {"none", "true", "false", "yes", "no", "ok", "n/a", "null",
        "and", "or", "the", "type", "left", "right", "center"}


def collect_labels_from_books() -> set[str]:
    """Английские строки, которые игрок видит в книгах:

    * метки ссылок внутри макросов  $(l:…)Метка$(/l), $(item)Метка$();
    * отдельные заголовки/названия полей ("Speed Array", "Ritual of Binding").

    Берутся только из СОБРАННОГО пака — там то, что реально видит игрок.
    """
    labels: set[str] = set()

    def scan_text(text: str) -> None:
        for m in LBL.finditer(text):
            t = (m.group(2) or "").strip()
            if not t or CYR.search(t):
                continue
            if ID.match(t) or not WORD.search(t):
                continue
            if "$(" in t:
                continue
            labels.add(t)

    def scan_value(text: str) -> None:
        t = text.strip()
        if len(t) < 3 or CYR.search(t):
            return
        if t[0] in "#$-/{" or "$(" in t or t.startswith("http"):
            return
        if "_" in t:
            return  # идентификатор (Alchemy_table), а не переводимый текст
        if ID.match(t) or not WORD.search(t):
            return
        if t.endswith((".png", ".jpg", ".jpeg", ".json", ".snbt")):
            return
        if t.lower() in STOP:
            return
        # переводим только то, что похоже на название/заголовок:
        # либо несколько слов, либо слово с большой буквы
        if " " not in t and not t[:1].isupper():
            return
        labels.add(t)

    stage = HERE / "pack_build"
    if not stage.exists():
        return labels
    for dp, _, fns in os.walk(stage / "assets"):
        if "patchouli_books" not in dp or "/ru_ru" not in dp:
            continue
        for fn in fns:
            if not fn.endswith(".json"):
                continue
            try:
                raw = open(os.path.join(dp, fn), encoding="utf-8").read()
            except Exception:
                continue
            scan_text(raw)
            try:
                data = json.loads(raw)
            except Exception:
                continue

            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if isinstance(v, str):
                            scan_value(v)
                        else:
                            walk(v)
                elif isinstance(o, list):
                    for v in o:
                        if isinstance(v, str):
                            scan_value(v)
                        else:
                            walk(v)

            walk(data)
    return labels


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    labels_ru: dict[str, str] = {}
    if LABELS_RU.exists():
        labels_ru = json.loads(LABELS_RU.read_text(encoding="utf-8"))
    labels = collect_labels_from_books()
    todo = sorted(t for t in labels if not labels_ru.get(t))
    print(f"английских меток ссылок: {len(labels)}, ещё не переведено: {len(todo)}")
    if args.dry_run:
        for t in todo[:25]:
            print("   ", repr(t[:80]))
        return 0
    if not todo:
        print("нечего переводить")
        return 0

    from deepseek_backend import DeepSeekBackend
    from fix_translate import Hints

    glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))
    mods_ru = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    po_ru = json.loads((WORK / "patchouli_ru.json").read_text(encoding="utf-8"))
    prot = Protector(glossary, mode="none", keep_spaces=True)
    hints = Hints(glossary, {**mods_ru, **po_ru})
    backend = DeepSeekBackend()

    masked = {t: prot.protect(t) for t in todo}
    chunks = [todo[i:i + args.batch] for i in range(0, len(todo), args.batch)]
    ok: dict[str, str] = {}
    bad: list[tuple[str, str]] = []
    done = [0]

    def do_chunk(chunk: list[str]):
        payload = [{"en": masked[s][0], "terms": hints.for_string(s)} for s in chunk]
        try:
            out = backend.translate_batch_hinted(payload)
        except Exception as exc:  # noqa: BLE001
            return [(s, "") for s in chunk]
        return [(s, restore_brands(s, prot.restore(ru, masked[s][1]))) for s, ru in zip(chunk, out)]

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for res in pool.map(do_chunk, chunks):
            for s, ru in res:
                if ru and ru.strip() and (CYR.search(ru) or not WORD.search(s)):
                    ok[s] = ru
                else:
                    bad.append((s, ru))
            done[0] += 1
            labels_ru.update(ok)
            LABELS_RU.write_text(json.dumps(labels_ru, ensure_ascii=False, indent=1), encoding="utf-8")
            if done[0] % 4 == 0 or done[0] == len(chunks):
                print(f"[{done[0]}/{len(chunks)}] готово: {len(ok)}, отбраковано: {len(bad)}, "
                      f"{time.time() - t0:.0f}s", flush=True)

    labels_ru.update(ok)
    LABELS_RU.write_text(json.dumps(labels_ru, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nпереведено: {len(ok)} → {LABELS_RU.name}")
    print(f"отбраковано: {len(bad)}")
    for s, ru in bad[:12]:
        print(f"   {s[:60]!r} -> {ru[:50]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
