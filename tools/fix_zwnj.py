"""Нормализация маркеров переноса ZWNJ (U+200C) в переводе квестов.

Что такое ZWNJ в оригинале (EN):
    слово + ZWNJ + один пробел + следующее слово
Это маркер переноса, оставленный автором пака. Инварианты оригинала:
  * ZWNJ никогда не стоит в начале строки;
  * перед ZWNJ никогда нет пробела;
  * после ZWNJ ровно один пробел;
  * два ZWNJ подряд не встречаются.

Перевод (DeepL/Google) маркеры растащил: появились "ZWNJ + два пробела",
"пробел + ZWNJ", "ZWNJ ZWNJ" — в игре это видно как лишние пробелы
(например "Как  лидер железных").

Скрипт пересобирает расстановку заново по образцу оригинала:
  * маркер ставится строго "слово + ZWNJ + один пробел";
  * позиция подбирается пропорционально позиции маркера в EN (по словам);
  * лишние пробелы, возникшие от размножения ZWNJ, схлопываются.

Замечание: в коде FTB Quests / FTB Library U+200C нигде не обрабатывается
(проверено поиском по байткоду), то есть маркер визуально невидим и влияет
только на пробелы вокруг себя. Поэтому точная позиция маркера косметична —
важно их количество и отсутствие «рваных» пробелов.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
Z = "\u200c"

sys.path.insert(0, str(HERE))
from tr_engine import RE_COLOR, RE_FILE, RE_HEX, RE_ID, RE_MARKUP, RE_PLACEHOLDER, RE_TAG, RE_URL  # noqa: E402
from polish_ru import apply_rules  # noqa: E402

# Всё, внутрь чего маркер ставить нельзя: теги <grad …>, цвета, {image:…},
# [item:…], плейсхолдеры и т.п. В EN маркер внутри таких конструкций не стоит.
PROTECT = re.compile("|".join(
    f"(?:{rx.pattern})" for rx in
    (RE_TAG, RE_MARKUP, RE_COLOR, RE_HEX, RE_PLACEHOLDER, RE_ID, RE_URL, RE_FILE)
))

TARGET = WORK / "quests_ru.json"
BACKUP = WORK / "quests_ru.pre_zwnjfix.json"


def clean_ru(ru: str) -> str:
    """Убрать ZWNJ, почистить пунктуацию и схлопнуть лишние пробелы."""
    s = ru.replace(Z, "")
    s = apply_rules(s)
    return s.strip()


def en_marker_fractions(en: str) -> list[float]:
    """Доля позиции каждого маркера в EN (0..1) — по границам слов.

    Маркер в EN стоит после слова: «слово<Z> следующее». Так что доля =
    (номер слова-носителя + 1) / всего слов.
    """
    chunks = en.split(Z)
    total = max(len(en.split()), 1)
    n_words = 0
    fracs: list[float] = []
    for ch in chunks[:-1]:
        n_words += len(ch.split())
        fracs.append(n_words / total)
    return fracs


def place_ru(ru: str, en: str) -> tuple[str, int]:
    """Пересобрать расстановку ZWNJ в переводе по образцу оригинала.

    Правило: маркер ставится сразу ПОСЛЕ слова и всегда перед пробелом
    («слово<Z> следующее»), как в оригинале. Поэтому последнее слово строки
    маркером не помечается — после него уже нечего ставить.

    Возвращает (новая строка, сколько маркеров не поместилось).
    """
    fracs = en_marker_fractions(en)
    if not fracs:
        return clean_ru(ru), 0

    s = clean_ru(ru)
    words = s.split(" ")
    if len(words) < 2:
        return s, len(fracs)

    n_ru = len(words)
    # маркер после words[k] — валидны k = 0..n_ru-2 (дальше нет пробела)
    n_pos = n_ru - 1
    pos_fracs = [(k + 1) / n_ru for k in range(n_pos)]

    # запрещённые позиции: пробел после слова внутри защищённой конструкции
    space_pos = []
    pos = 0
    for w in words[:-1]:
        pos += len(w)
        space_pos.append(pos)
        pos += 1
    forbidden = set()
    for m in PROTECT.finditer(s):
        for k, sp in enumerate(space_pos):
            if m.start() < sp < m.end():
                forbidden.add(k)

    used: set[int] = set()
    last = -1
    for f in fracs:
        cands = [k for k in range(n_pos) if k not in used and k > last and k not in forbidden]
        if not cands:
            continue
        k = min(cands, key=lambda k: abs(pos_fracs[k] - f))
        used.add(k)
        last = k

    parts = []
    for i, w in enumerate(words):
        parts.append(w)
        if i in used:
            parts.append(Z)
        if i != len(words) - 1:
            parts.append(" ")
    return "".join(parts), len(fracs) - len(used)


def main() -> int:
    if not TARGET.exists():
        raise SystemExit("нет work/quests_ru.json")
    if "--from-backup" in sys.argv and BACKUP.exists():
        # старт с «чистого» состояния (иначе правка идемпотентна)
        shutil.copy2(BACKUP, TARGET)
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    if not BACKUP.exists():
        shutil.copy2(TARGET, BACKUP)

    changed = 0
    lost = 0
    punct_fixed = 0
    for en, ru in list(data.items()):
        if not isinstance(ru, str):
            continue
        if Z in en or Z in ru:
            new, dropped = place_ru(ru, en)
            lost += dropped
        else:
            new = apply_rules(ru)
        if new != ru:
            changed += 1
            if apply_rules(ru) != ru:
                punct_fixed += 1
            data[en] = new

    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    bad = []
    for en, ru in data.items():
        if not isinstance(ru, str) or Z not in ru:
            continue
        if re.search(r"[ ]" + Z, ru) or re.search(Z + Z, ru) or re.search(Z + r"[ ]{2,}", ru):
            bad.append(("форма", en, ru))
        elif ru.endswith(Z) or ru.startswith(Z):
            bad.append(("маркер на краю строки", en, ru))
        elif re.search(Z + r"(?![ ])", ru):
            bad.append(("за маркером не пробел", en, ru))
        elif ru.count(Z) > en.count(Z):
            bad.append(("больше маркеров", en, ru))
        else:
            # маркер не должен попадать внутрь разметки
            for m in PROTECT.finditer(ru):
                if Z in ru[m.start():m.end()]:
                    bad.append(("внутри разметки", en, ru))
                    break
    print(f"строк изменено: {changed}")
    print(f"из них исправлено пунктуации: {punct_fixed}")
    print(f"маркеров не поместилось (в RU меньше слов, чем маркеров в EN): {lost}")
    print(f"нарушений инвариантов после правки: {len(bad)}")
    for why, en, ru in bad[:5]:
        print(" ", why, "|", repr(en)[:80], "->", repr(ru)[:80])
    return 0


if __name__ == "__main__":
    sys.exit(main())
