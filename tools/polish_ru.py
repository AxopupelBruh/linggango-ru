"""Полировка русского текста перевода: пунктуация и единообразие «ё».

Что чиним:
  1. Артефакты машинного перевода: «пор .», «ауру ,», «( слово )», «[ текст ]».
  2. Смешение «е»/«ё» в одном слове: «серьезным» рядом с «ещё».

Как:
  * разметка (теги <grad …>, {image:…}, [item:…], цвета, ID, ссылки) не трогается —
    она защищена теми же регулярками, что и в основном пайплайне;
  * «ё» приводится к единому виду: если слово встречается и с «ё», и с «е»,
    оставляем «ё» (правильная форма). Исключения — слова, где «е» и «ё» —
    РАЗНЫЕ слова: все/всё, всего/всёго, всем/всём, чем/чём, рев/рёв,
    порченных/порчённых, тесаный/тёсаный, зелье/зельё, берет/берёт,
    сфера/сфёра, гети/гёти.

Скрипт идемпотентный: запускать можно многократно.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
sys.path.insert(0, str(HERE))
from tr_engine import (RE_COLOR, RE_FILE, RE_HEX, RE_ID, RE_MARKUP,  # noqa: E402
                       RE_PLACEHOLDER, RE_TAG, RE_URL)

Z = "\u200c"

FILES = ["quests_ru.json", "mods_ru.json", "kubejs_ru.json",
         "extra_ru.json", "patchouli_ru.json"]

PROTECT = re.compile("|".join(
    f"(?:{rx.pattern})" for rx in
    (RE_TAG, RE_MARKUP, RE_COLOR, RE_HEX, RE_PLACEHOLDER, RE_ID, RE_URL, RE_FILE)
))

# --- правила пунктуации -------------------------------------------------
RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[ \t]{2,}"), " "),
    (re.compile(r"[ \t]+([,;:!?])"), r"\1"),
    (re.compile(r"(?<=[^\s\d.,!?])[ \t]+\.(?=\s|$|‌|\x00)"), ""),
    (re.compile(r"[ \t]+([)»])"), r"\1"),
    (re.compile(r"([(«])[ \t]+"), r"\1"),
]

# --- слова, где «е» и «ё» — разные слова -------------------------------
YO_EXCLUDE = {
    "все", "всего", "всем", "чем", "рев", "порченных", "тесаный",
    "зелье", "берет", "сфера", "гети",
}

RE_WORD = re.compile(r"[А-Яа-яЁё]+")


def apply_rules(s: str) -> str:
    for rx, rep in RULES:
        s = rx.sub(rep, s)
    return s


def yo_map(corpora: list[list[str]]) -> dict[str, str]:
    """Словарь: слово с «е» → слово с «ё» (только однозначные случаи)."""
    forms: set[str] = set()
    for vals in corpora:
        for v in vals:
            for w in RE_WORD.findall(v):
                forms.add(w.lower())

    pairs: dict[str, str] = {}
    for w in forms:
        if "ё" not in w:
            continue
        e = w.replace("ё", "е")
        if e in forms and e not in YO_EXCLUDE and w.replace("ё", "е") not in YO_EXCLUDE:
            pairs[e] = w
    return pairs


def apply_yo(s: str, pairs: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        w = m.group(0)
        low = w.lower()
        if "ё" in low:
            return w
        target = pairs.get(low)
        if not target:
            return w
        if w[0].isupper():
            return target[0].upper() + target[1:]
        return target

    return RE_WORD.sub(repl, s)


def segments(s: str):
    """Разбить строку на (текст, защищённый) части — разметку не трогаем."""
    spans = [(m.start(), m.end()) for m in PROTECT.finditer(s)]
    if not spans:
        yield s, False
        return
    pos = 0
    for a, b in spans:
        if a > pos:
            yield s[pos:a], False
        yield s[a:b], True
        pos = b
    if pos < len(s):
        yield s[pos:], False


PH = "\x00{:04d}\x00"
PH_RE = re.compile("\x00(\\d{4})\x00")


def polish(s: str, pairs: dict[str, str]) -> str:
    """Разметку прячем под плейсхолдеры, правила применяем к целой строке,
    потом возвращаем разметку на место.

    Плейсхолдеры фиксированной ширины: иначе «\\x0012\\x00» может случайно
    встретиться внутри «\\x001\\x002\\x00» и восстановление собьётся.
    """
    spans = [(m.start(), m.end()) for m in PROTECT.finditer(s)]
    frags: list[str] = []
    out: list[str] = []
    pos = 0
    for a, b in spans:
        out.append(s[pos:a])
        frags.append(s[a:b])
        out.append(PH.format(len(frags) - 1))
        pos = b
    out.append(s[pos:])

    tmp = "".join(out)
    tmp = apply_rules(tmp)
    tmp = apply_yo(tmp, pairs)

    return PH_RE.sub(lambda m: frags[int(m.group(1))], tmp)


def main() -> int:
    data: dict[str, dict] = {}
    for f in FILES:
        p = WORK / f
        if p.exists():
            data[f] = json.loads(p.read_text(encoding="utf-8"))

    corpora = [[v for v in d.values() if isinstance(v, str)] for d in data.values()]
    pairs = yo_map(corpora)
    print(f"однозначных пар е/ё: {len(pairs)}")

    for f, d in data.items():
        changed = 0
        for k, v in list(d.items()):
            if not isinstance(v, str):
                continue
            new = polish(v, pairs)
            if new != v:
                changed += 1
                d[k] = new
        (WORK / f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{f}: изменено строк — {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
