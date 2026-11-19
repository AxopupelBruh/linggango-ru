"""Применяет переводы к конфигам сборки (меню классов, подсказки, сложности, механизмы).

Читает:
  work/extra_items.json — план (что и где переводить)
  work/extra_ru.json    — переводы {исходный текст: русский}

Перед записью делает бэкап в backup/config_extra/.
"""
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = INSTANCE
WORK = HERE / "work"
BACKUP = HERE / "backup/config_extra"

sys.path.insert(0, str(HERE))
from collect_extra import TIP_LABELS  # noqa: E402


def backup(rel: str) -> None:
    src = ROOT / rel
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)


def read_raw(path: Path) -> str:
    """Читаем файл, не трогая переводы строк (CRLF/LF сохраняются)."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_raw(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def set_path(obj, path, value):
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value


# ---------------------------------------------------------------------------
# Применение к JSON
# ---------------------------------------------------------------------------

def apply_json(rel: str, edits: list[tuple[list, str]]) -> None:
    backup(rel)
    f = ROOT / rel
    data = json.loads(read_raw(f))
    for path, value in edits:
        set_path(data, path, value)
    write_raw(f, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Применение к TOML (построчно, с учётом секций)
# ---------------------------------------------------------------------------

RE_TOML_HEAD = re.compile(r"^\s*\[([^\]]+)\]\s*$")
RE_TOML_STR = re.compile(r'^(\s*)([A-Za-z0-9_\-]+)(\s*=\s*)"(.*)"(\s*)$')


def split_header(h: str) -> list[str]:
    return [p.strip().strip('"').strip("'") for p in h.split(".")]


def apply_toml(rel: str, edits: list[tuple[list, str]]) -> None:
    backup(rel)
    f = ROOT / rel
    lines = read_raw(f).splitlines(keepends=True)
    want: dict[tuple[str, ...], str] = {}
    for path, value in edits:
        want[(tuple(path[:-1]), path[-1])] = value
    cur: list[str] = []
    changed = 0
    for i, line in enumerate(lines):
        mh = RE_TOML_HEAD.match(line)
        if mh:
            cur = split_header(mh.group(1))
            continue
        ms = RE_TOML_STR.match(line.rstrip("\n"))
        if not ms:
            continue
        key = (tuple(cur), ms.group(2))
        if key not in want:
            continue
        val = want[key]
        eol = "\n" if line.endswith("\n") else ""
        lines[i] = f'{ms.group(1)}{ms.group(2)}{ms.group(3)}"{val}"{ms.group(5)}{eol}'
        changed += 1
    write_raw(f, "".join(lines))
    if changed != len(edits):
        print(f"  ! {rel}: заменено {changed} из {len(edits)}")


# ---------------------------------------------------------------------------
# Применение к списку подсказок (TOML-массив в одну строку)
# ---------------------------------------------------------------------------

RE_TIPSLIST = re.compile(r"^(\s*tipsList\s*=\s*)(\[.*\])(\s*)$", re.M)


def apply_tips(rel: str, edits: list[tuple[int, str]]) -> None:
    backup(rel)
    f = ROOT / rel
    raw = read_raw(f)
    m = RE_TIPSLIST.search(raw)
    if not m:
        print(f"  ! {rel}: не найдена строка tipsList")
        return
    arr = json.loads(m.group(2))
    for idx, value in edits:
        arr[idx] = value
    new_line = m.group(1) + json.dumps(arr, ensure_ascii=False) + m.group(3)
    raw = raw[:m.start()] + new_line + raw[m.end():]
    write_raw(f, raw)


def apply_fixed(rel: str, key: str, value: str) -> None:
    backup(rel)
    f = ROOT / rel
    raw = read_raw(f)
    pat = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*)"[^"]*"', re.M)
    raw, n = pat.subn(lambda m: m.group(1) + '"' + value + '"', raw, count=1)
    write_raw(f, raw)


def main() -> None:
    items = json.loads((WORK / "extra_items.json").read_text(encoding="utf-8"))
    ru_map = json.loads((WORK / "extra_ru.json").read_text(encoding="utf-8"))

    json_edits: dict[str, list] = defaultdict(list)
    toml_edits: dict[str, list] = defaultdict(list)
    tip_edits: dict[str, list] = defaultdict(list)
    fixed: list[tuple[str, str, str]] = []

    missing = 0
    for it in items:
        kind = it["kind"]
        rel = it["file"]
        if kind == "fixed":
            fixed.append((rel, it["key"], it["ru"]))
            continue
        ru = ru_map.get(it["text"])
        if ru is None:
            missing += 1
            continue
        if kind == "json":
            json_edits[rel].append((it["path"], ru))
        elif kind == "toml":
            toml_edits[rel].append((it["path"], ru))
        elif kind == "tip":
            label = it.get("label")
            label_ru = TIP_LABELS.get(label, label) if label else ""
            prefix = it.get("prefix") or ""
            value = f"{prefix}{label_ru}|{ru}" if label else f"{prefix}{ru}"
            tip_edits[rel].append((it["index"], value))

    if missing:
        print(f"  ! без перевода осталось {missing} мест — они останутся как есть")

    for rel, edits in json_edits.items():
        apply_json(rel, edits)
        print(f"  json  {rel}: {len(edits)}")
    for rel, edits in toml_edits.items():
        apply_toml(rel, edits)
        print(f"  toml  {rel}: {len(edits)}")
    for rel, edits in tip_edits.items():
        apply_tips(rel, edits)
        print(f"  tips  {rel}: {len(edits)}")
    for rel, key, value in fixed:
        apply_fixed(rel, key, value)
        print(f"  fixed {rel}: {key}")


if __name__ == "__main__":
    main()
