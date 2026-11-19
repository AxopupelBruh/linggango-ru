"""Генерирует блок ClientEvents.lang("ru_ru", ...) для kubejs/client_scripts/lang.js.

В оригинале переименования предметов есть только для en_us, поэтому в русской
локали эти 64 предмета показываются дефолтными (или английскими) названиями.
Здесь берём английские названия из lang.js и подставляем русские из переводов.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LANG_JS = ROOT / "kubejs/client_scripts/lang.js"
WORK = HERE / "work"


def main():
    src = LANG_JS.read_text(encoding="utf-8")
    renames = re.findall(r"event\.renameItem\('([^']+)',\s*'((?:[^'\\]|\\.)*)'\)", src)
    adds = re.findall(r"event\.add\('([^']+)',\s*'((?:[^'\\]|\\.)*)'\)", src)
    print(f"найдено renameItem: {len(renames)}, add: {len(adds)}")

    tr = {}
    p = WORK / "kubejs_ru.json"
    if p.exists():
        tr = json.loads(p.read_text(encoding="utf-8"))

    lines = []
    missing = []
    for item_id, name in renames:
        ru = tr.get(name)
        if not ru:
            missing.append((item_id, name))
            continue
        lines.append(f" event.renameItem('{item_id}', '{ru}')")
    for key, value in adds:
        ru = tr.get(value)
        if not ru:
            missing.append((key, value))
            continue
        lines.append(f" event.add('{key}', '{ru}')")

    if missing:
        print(f"БЕЗ ПЕРЕВОДА ({len(missing)}):")
        for i, n in missing[:20]:
            print(f"   {i} :: {n}")

    block = ('\n// Русская локализация: те же переименования, что и для en_us\n'
             'ClientEvents.lang("ru_ru", event => {\n'
             + "\n".join(lines) + "\n});\n")

    out = LANG_JS.read_text(encoding="utf-8")
    if 'ClientEvents.lang("ru_ru"' in out:
        print("блок ru_ru уже есть — заменяю")
        out = re.sub(r'\n// Русская локализация.*?\n\}\);\n', block, out, flags=re.S)
    else:
        out = out.rstrip() + "\n" + block
    LANG_JS.write_text(out, encoding="utf-8")
    print(f"записано строк в ru_ru-блок: {len(lines)}")


if __name__ == "__main__":
    main()
