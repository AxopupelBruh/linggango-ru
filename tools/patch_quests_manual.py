"""Точечная правка оставшихся английских строк в файлах FTB Quests.

Разделители ZWNJ (\u200c) могут быть записаны в файле как escape-последовательность
или как сам символ — паттерны строятся терпимо к обоим вариантам.
Разметка custom-text (<grad>, <shadow>) сохраняется как есть.
"""
import re, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lgq_crypt as C

ROOT = Path(__file__).resolve().parent.parent
QUESTS = ROOT / "config/ftbquests/quests"
BACKUP = Path(__file__).resolve().parent / "backup/quests_original"

Z = r"(?:‌|\\u200c)"

REPL = [
    (r"Heavy", "Тяжёлый"),
    (r"Quick", "Быстрый"),
    (r"The" + Z + r"\s*Workbench", "Рабочий верстак"),
    (r"Same" + Z + r"\s*Flight,\s*No" + Z + r"\s*Slot Used", "Тот же полёт — слот не нужен"),
    (r"One Charge,\s*Four" + Z + r"\s*Pieces", "Одна зарядка — четыре детали"),
    (r"Puts" + Z + r"\s*your" + Z + r"\s*absorbed" + Z + r"\s*radiation" + Z + r"\s*dose" + Z +
     r"\s*on" + Z + r"\s*the" + Z + r"\s*suit" + Z + r"\s*overlay" + Z + r"\s*so" + Z + r"\s*you" + Z +
     r"\s*find" + Z + r"\s*out" + Z + r"\s*before" + Z + r"\s*it" + Z + r"\s*starts" + Z + r"\s*hurting\.",
     "Показывает поглощённую дозу радиации на оверлее костюма — вы узнаете об этом до того, как начнёте страдать."),
    (r"Nether stars,\s*ultimate" + Z + r"\s*alloy,\s*an\s*ultimate" + Z + r"\s*induction" + Z +
     r"\s*provider" + Z + r"\s*and" + Z + r"\s*an\s*", "Незеритовые звёзды, высший сплав, высший индуктор и "),
    (r"antimatter" + Z + r"\s*pellet", "античастица"),
    (r"It" + Z + r"\s*also" + Z + r"\s*lets" + Z + r"\s*you" + Z + r"\s*sprint" + Z + r"\s*while" + Z +
     r"\s*your" + Z + r"\s*hunger" + Z + r"\s*bar" + Z + r"\s*is\s+empty,\s*which" + Z + r"\s*the" + Z +
     r"\s*Nutritional" + Z + r"\s*Injection" + Z + r"\s*Unit" + Z + r"\s*already" + Z + r"\s*makes" + Z + r"\s*moot\.",
     "Также позволяет бегать при пустой полосе голода, что уже делает бессмысленным Модуль питания."),
    (r"You" + Z + r"\s*can" + Z + r"\s*also" + Z + r"\s*use" + Z + r"\s*items" + Z + r"\s*at" + Z +
     r"\s*full" + Z + r"\s*speed" + Z + r"\s*while" + Z + r"\s*sprinting" + Z + r"\s*or" + Z + r"\s*flying\.",
     "Также можно использовать предметы на полной скорости во время бега или полёта."),
    (r"Fires arrows made of energy for\s*", "Стреляет энергетическими стрелами, наносящими "),
    (r"\s*extra per shot,\s*so you never carry arrows again\.",
     " дополнительного урона за выстрел — вам больше не нужно носить стрелы."),
]

def main():
    changed_files = 0
    changed_hits = 0
    for f in sorted(QUESTS.rglob("*.snbt")):
        rel = f.relative_to(QUESTS)
        raw = f.read_text(encoding="utf-8")
        enc = C.is_encrypted(raw)
        plain = C.decrypt(raw) if enc else raw
        new = plain
        hits = 0
        for pat, rep in REPL:
            new, n = re.subn(pat, rep, new)
            hits += n
        if hits and new != plain:
            bak = BACKUP / rel
            bak.parent.mkdir(parents=True, exist_ok=True)
            if not bak.exists():
                bak.write_text(raw, encoding="utf-8")
            f.write_text(C.encrypt(new) if enc else new, encoding="utf-8")
            changed_files += 1
            changed_hits += hits
            print(f"  {rel}: {hits} замен")
    print(f"файлов изменено: {changed_files}, замен: {changed_hits}")

if __name__ == "__main__":
    main()
