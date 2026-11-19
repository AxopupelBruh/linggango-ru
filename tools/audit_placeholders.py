"""Детектор переведённых плейсхолдеров и ключей в словарях перевода.

Плейсхолдеры вида <n>, <name>, <list>, §adifficulty.<n> — это синтаксис модов,
их переводить нельзя: конфиг перестанет работать.

Проверяем:
  * §-коды с кириллицей внутри (§aсложность);
  * угловые плейсхолдеры EN, которых нет в RU (или заменены на другие);
  * одинаковые плейсхолдеры, но с разным содержимым.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

RE_COLOR_KEY = re.compile(r"§[a-zA-Z][^\s=]*")
RE_PH = re.compile(r"<([^<>]{1,60})>")
# настоящий ключ конфига: §a + текст + .<n> или =<...>
RE_CFG_KEY = re.compile(r"§[a-zA-Z][^\s]*\.(?:<[^>]+>|\w+)\s*=")
RE_KEY_PART = re.compile(r"§[a-zA-Z][^\s=]*(?=\.)")


def is_placeholder(text: str) -> bool:
    """Похоже на плейсхолдер, а не на обычный текст в скобках."""
    if " " in text:
        return False
    if re.search(r"[А-Яа-яЁё]", text):
        return False
    return True


def check(name: str, data: dict) -> None:
    key_bad: list[str] = []
    ph_bad: list[str] = []
    for en, ru in data.items():
        if not isinstance(ru, str) or not isinstance(en, str):
            continue
        # §-ключи с кириллицей
        for m in RE_COLOR_KEY.finditer(ru):
            if re.search(r"[А-Яа-яЁё]", m.group(0)):
                key_bad.append(f"{en[:70]} :: {m.group(0)}")
                break
        # плейсхолдеры
        en_ph = [p for p in RE_PH.findall(en) if is_placeholder(p)]
        ru_ph = RE_PH.findall(ru)
        ru_set = set(ru_ph)
        lost = [p for p in en_ph if p not in ru_set]
        if lost:
            ph_bad.append(f"{en[:70]} :: потеряно {lost} → есть {sorted(ru_set)[:6]}")
    print(f"\n### {name}: записей {len(data)}")
    print(f"  §-ключи с кириллицей: {len(key_bad)}")
    for x in key_bad[:25]:
        print("   ", x)
    print(f"  потерянные плейсхолдеры: {len(ph_bad)}")
    for x in ph_bad[:25]:
        print("   ", x)


def main() -> None:
    for fname in ("quests_ru.json", "mods_ru.json", "ui_strings_ru.json",
                  "patchouli_ru.json", "extra_ru.json"):
        p = WORK / fname
        if not p.exists():
            continue
        check(fname, json.loads(p.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
