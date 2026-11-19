"""Раунд правок после вычитки: названия классов, названия клавиш, огрехи перевода.

Правится словари work/<source>_ru.json (то, что потом уходит в игру).
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
sys.path.insert(0, str(HERE))
from manual_classes import CLASS_DESCRIPTIONS, CLASS_NAMES  # noqa: E402


def load(name):
    p = WORK / f"{name}.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    total = 0

    # --- классы ---
    p, data = load("extra_ru")
    n = 0
    for en, ru in CLASS_NAMES.items():
        if en in data and data[en] != ru:
            data[en] = ru
            n += 1
    for en, ru in CLASS_DESCRIPTIONS.items():
        if en in data and data[en] != ru:
            data[en] = ru
            n += 1
    save(p, data)
    print(f"классы: заменено {n}")
    total += n

    # --- названия клавиш (по ванильной русской локализации) ---
    KEY_FIXES = [
        # отдельные подписи клавиш
        ("mods", {"SHIFT": "Shift", "ALT": "Alt"}),
        # клавиша в тексте
        ("mods", {"-Удерживайте сдвиг, чтобы получить дополнительную информацию-":
                  "-Удерживайте Shift, чтобы получить дополнительную информацию-",
                  "§7Удерживайте правую кнопку мыши + сдвиг в течение 0,5 секунды":
                  "§7Удерживайте правую кнопку мыши + Shift в течение 0,5 секунды"}),
        # способность: название из lang-файла мода
        ("quests", {"Сингулярность\u200c Сдвиг": "Сдвиг сингулярности"}),
    ]
    for src, fixes in KEY_FIXES:
        p, data = load(f"{src}_ru")
        n = 0
        for en, ru in fixes.items():
            if en in data and data[en] != ru:
                data[en] = ru
                n += 1
        save(p, data)
        print(f"{src}: клавиши/названия — {n}")
        total += n

    # --- kubejs: подсказка с сочетаниями клавиш ---
    p, data = load("kubejs_ru")
    n = 0
    for k, v in data.items():
        if "Общие элементы управления" in v:
            new = (v.replace("Вкладка; Следующая глава", "Tab; Следующая глава")
                    .replace("Пространство; Перецентрировать вид", "Пробел; Перецентрировать вид")
                    .replace("Левая кнопка мыши; Просмотреть подробности задания",
                             "ЛКМ; Просмотреть подробности задания")
                    .replace("Ctrl + левая кнопка мыши", "Ctrl + ЛКМ")
                    .replace("Средняя кнопка мыши", "СКМ")
                    .replace("Правая кнопка мыши", "ПКМ")
                    .replace("Middle Mouse: Drag", "СКМ: перетаскивание")
                    .replace("Ctrl + Middle Mouse: Drag", "Ctrl + СКМ: перетаскивание"))
            if new != v:
                data[k] = new
                n += 1
        elif "Режим редактирования" in v:
            new = (v.replace("Вставить Quest (без зависимостей)", "Вставить квест (без зависимостей)")
                    .replace("Во время выполнения задания Парение отображать подробную информацию",
                             "При наведении на квест показывать подробную информацию"))
            if new != v:
                data[k] = new
                n += 1
    save(p, data)
    print(f"kubejs: клавиши — {n}")
    total += n

    print(f"всего замен: {total}")


if __name__ == "__main__":
    main()
