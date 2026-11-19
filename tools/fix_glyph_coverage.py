"""Убираем символы, для которых в ванильном шрифте 1.20.1 нет глифов.

Если символ не покрыт шрифтом, в игре он рисуется пустым квадратом.
Проверенные замены (все — с покрытым глифом):

  遮罩        → маска            (ending_library)
  坂上駒子    → Сакагами Комико  (goety, имя статуэтки)
  『』        → «»              (goetyawaken)
  ！          → !               (goetyawaken, patchouli)
  。          → .               (patchouli, китайская точка)
  ，          → ,               (create new age)
  ～          → ~               (create new age)
  （          → (               (goety, книга)
  ・          → • / ·           (weapon, маркер списка / разделитель)
  ꭀ ꭁ ꭈ ꭉ  → œ ø ø ɾ         (simplyswords, декоративные буквы)
  需求        → Требования       (книга, китайский)
  给予食用者  → Выдаётся игроку  (книга, китайский)
  炽热气场    → Огненная аура
  舒适        → Комфорт
  分钟        → минут
  ➤          → →               (квесты)
  📐 / 🟫    → △ / ■            (скрипт подсказок)

Что НЕ трогаем:
  * `#➤❓-questions` — это имя Discord-канала, его нельзя менять;
  * `Игрушка §a東漢 駒§r` — собственный русский перевод мода goety;
  * эмодзи и значки из оригинальных en_us модов (💧💥🪄✖…): они есть и
    в английском варианте, это стиль авторов модов.

Что делаем:
  1) правим work/*.json — источник правды;
  2) правим живые .snbt квестов (расшифровка LGQ1 → замена → шифрование);
  3) пересобираем ресурспак, датапак и скрипт подсказок.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import INSTANCE, WORK_DIR  # noqa: E402
import lgq_crypt as C  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = INSTANCE
QUESTS = ROOT / "config/ftbquests/quests"
WORK = HERE / "work"

# --- точные замены в значениях переводов -------------------------------
EXACT: dict[str, list[tuple[str, str]]] = {
    "mods_ru.json": [
        ("Текстура маски с резной тыквой головой Текстура 遮罩",
         "Текстура маски с резной тыквой головой (маска)"),
        ("Статуэтка §a坂上駒子", "Статуэтка §aСакагами Комико"),
        ("『Клинок Заката』Яйцо призывания Розалин",
         "«Клинок Заката» Яйцо призывания Розалин"),
        ("Арка！", "Арка!"),
    ],
    "patchouli_ru.json": [
        ("需求: ", "Требования: "),
        ("给予食用者:$(br)$(li)5分钟的炽热气场,$(li)5分钟的舒适",
         "Выдаётся игроку:$(br)$(li)Огненная аура на 5 минут,$(li)Комфорт на 5 минут"),
        ("『Клинок Заката』Розалин", "«Клинок Заката» Розалин"),
        ("...！", "...!"),
        ("легенды。", "легенды."),
        ("состояние。", "состояние."),
        ("тёмную кухню... （ ", "тёмную кухню... ( "),
    ],
    "quests_ru.json": [
        ("-➤ ", "-→ "),
    ],
    "runtime_missing_ru.json": [
        ("📐 ", "△ "),
        ("🟫", "■"),
    ],
    "runtime_manual_ru.json": [
        ("📐 ", "△ "),
        ("🟫", "■"),
    ],
}

# --- посимвольные замены (применяются после точных) ---------------------
CHAR: dict[str, list[tuple[str, str]]] = {
    "mods_ru.json": [
        ("，", ","),
        ("～", "~"),
        ("ꭀ", "œ"),
        ("ꭁ", "ø"),
        ("ꭈ", "ø"),
        ("ꭉ", "ɾ"),
    ],
}

# маркер списка в подсказках weapon: "§7・" → "§7•", иначе "・" → "·"
RE_BULLET = re.compile(r"§7・")
RE_MIDDOT = re.compile(r"・")


def fix_dicts() -> int:
    total = 0
    for fname, pairs in EXACT.items():
        p = WORK / fname
        if not p.exists():
            print(f"  пропуск {fname} — нет файла")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        n = 0
        for k, v in list(d.items()):
            if not isinstance(v, str):
                continue
            s = v
            for old, new in pairs:
                if old in s:
                    s = s.replace(old, new)
                    n += 1
            if fname in CHAR:
                for old, new in CHAR[fname]:
                    if old in s:
                        s = s.replace(old, new)
                        n += 1
            if fname == "mods_ru.json" and "・" in s:
                # сначала маркер списка, потом всё остальное — разделитель
                s = RE_BULLET.sub("§7•", s)
                s = RE_MIDDOT.sub("·", s)
                n += 1
            if s != v:
                d[k] = s
        if n:
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {fname}: замен {n}")
        total += n
    return total


def fix_quests() -> int:
    """Правим живые .snbt: ➤ → → (и на всякий случай ？！『』。，（）)."""
    rules = [("➤", "→"), ("！", "!"), ("『", "«"), ("』", "»"),
             ("。", "."), ("，", ","), ("～", "~"), ("（", "(")]
    hits = 0
    for f in sorted(QUESTS.rglob("*.snbt")):
        raw = f.read_text(encoding="utf-8")
        enc = C.is_encrypted(raw)
        plain = C.decrypt(raw) if enc else raw
        new = plain
        n = 0
        for old, rep in rules:
            c = new.count(old)
            if c:
                new = new.replace(old, rep)
                n += c
        if n and new != plain:
            out = C.encrypt(new) if enc else new
            f.write_text(out, encoding="utf-8")
            hits += n
            print(f"  {f.relative_to(QUESTS)}: {n}")
    return hits


def main() -> None:
    print("справочники переводов:")
    a = fix_dicts()
    print("живые квесты:")
    b = fix_quests()
    print(f"итого замен: {a + b}")


if __name__ == "__main__":
    main()
