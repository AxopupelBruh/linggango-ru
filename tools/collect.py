"""Собирает все строки, требующие перевода, из четырёх источников.

Источники:
  1. моды     — lang-файлы, где ключа нет в ru_ru (33 864 ключа)
  2. kubejs   — lang-файлы сборки (1 031 ключ)
  3. patchouli— страницы книг, где нет папки ru_ru
  4. квесты   — title/subtitle/hover из расшифрованных FTB-файлов

Результат: work/<source>.json = {уникальный исходный текст: [список мест]}
"""
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE, WORK_DIR  # noqa: E402
import snbt_text  # noqa: E402
from lang_json import load_lang_json  # noqa: E402

ROOT = INSTANCE
HERE = Path(__file__).parent
WORK = HERE / "work"
MODS = ROOT / "mods"
PLAIN = HERE / "plain"

TEXT_FIELDS = ("title", "subtitle", "description")


def collect_mods():
    en_by_ns, ru_by_ns = defaultdict(dict), defaultdict(dict)
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "/lang/" not in name:
                continue
            folder, fname = name.rsplit("/", 1)
            if fname not in ("en_us.json", "ru_ru.json"):
                continue
            try:
                data = load_lang_json(z.read(name))
            except Exception:
                continue
            ns = folder.split("/")[1]
            (en_by_ns if fname == "en_us.json" else ru_by_ns)[ns].update(data)
    out = {}
    for ns, en in en_by_ns.items():
        ru = ru_by_ns.get(ns, {})
        for key, val in en.items():
            if key in ru or not isinstance(val, str):
                continue
            out.setdefault(val, []).append(f"{ns}:{key}")
    return out


def collect_kubejs():
    out = {}
    for f in sorted((ROOT / "kubejs/assets").glob("*/lang/en_us.json")):
        ns = f.parent.parent.name
        data = json.loads(f.read_text(encoding="utf-8"))
        for key, val in data.items():
            if not isinstance(val, str):
                continue
            out.setdefault(val, []).append(f"kubejs/{ns}:{key}")
    return out


def collect_patchouli():
    out = {}
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "patchouli_books" not in name or not name.endswith(".json"):
                continue
            parts = name.split("/")
            try:
                i = parts.index("patchouli_books")
            except ValueError:
                continue
            if len(parts) <= i + 2 or parts[i + 2] != "en_us":
                continue
            book = parts[i + 1]
            ns = parts[i - 1]
            try:
                data = load_lang_json(z.read(name))
            except Exception:
                continue
            texts = []

            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k in ("text", "title", "description", "subtitle", "header",
                                 "footer", "name") and isinstance(v, str):
                            texts.append(v)
                        else:
                            walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(data)
            for t in texts:
                if t.strip():
                    out.setdefault(t, []).append(f"{jar.stem}:{ns}/{book}{name.split('en_us', 1)[1]}")
    return out


def collect_quests():
    """Собираем ВСЕ текстовые поля: title, subtitle, description (список!), hover."""
    out = {}
    for f in sorted(PLAIN.rglob("*.snbt")):
        raw = f.read_text(encoding="utf-8")
        rel = f.relative_to(PLAIN).as_posix()
        for key, text, _s, _e in snbt_text.iter_texts(raw):
            if text.strip():
                out.setdefault(text, []).append(f"{rel}:{key}")
    return out


COLLECTORS = {
    "quests": collect_quests,
    "kubejs": collect_kubejs,
    "mods": collect_mods,
    "patchouli": collect_patchouli,
}


def main():
    WORK.mkdir(exist_ok=True)
    for name, fn in COLLECTORS.items():
        data = fn()
        chars = sum(len(k) for k in data)
        (WORK / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name:11s} {len(data):7,} строк  {chars:9,} символов")


if __name__ == "__main__":
    main()
