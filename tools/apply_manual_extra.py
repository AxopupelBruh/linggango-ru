"""Собирает финальный перевод конфигов: база — Google, поверх — ручной словарь.

Вход : work/extra_ru_google_raw.json  (перевод переводчика без починки терминов)
Выход: work/extra_ru.json             (то, что пойдёт в конфиги сборки)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
sys.path.insert(0, str(HERE))
from manual_extra import PROSE, STATS  # noqa: E402


def main() -> None:
    raw = json.loads((WORK / "extra_ru_google_raw.json").read_text(encoding="utf-8"))
    data = dict(raw)
    n_stats = n_prose = 0
    for src, ru in STATS.items():
        if src in data and data[src] != ru:
            data[src] = ru
            n_stats += 1
    for src, ru in PROSE.items():
        if src in data and data[src] != ru:
            data[src] = ru
            n_prose += 1
    (WORK / "extra_ru.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # отчёт: что осталось на английском
    left = [(k, v) for k, v in data.items()
            if not any("Ѐ" <= ch <= "ӿ" for ch in v) and any(c.isalpha() for c in k)]
    print(f"строк: {len(data)}  ручных характеристик: {n_stats}  ручных фраз: {n_prose}")
    print(f"без кириллицы: {len(left)}")
    for k, v in left[:40]:
        print(f"  EN: {k[:100]!r}\n   RU: {v[:100]!r}")


if __name__ == "__main__":
    main()
