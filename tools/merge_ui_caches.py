"""Слияние кэшей перевода и сборка итогового словаря.

Два пула (по разным API-ключам) пишут в свои кэши; этот скрипт сливает их,
проверяет качество каждого перевода и собирает work/ui_strings_ru.json.

Запуск: python3 merge_ui_caches.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from fix_ui_brands import build_brands  # noqa: E402
from translate_ui_deepseek import BrandMasker, validate  # noqa: E402

CODE_RE = re.compile(r"§[0-9a-fk-orA-FK-OR]")


def _subseq(a: list[str], b: list[str]) -> bool:
    it = iter(b)
    return all(x in it for x in a)


def validate_codes(src: str, ru: str) -> bool:
    """Как validate(), но допускает перестановку/лишний §-код в конце.

    DeepSeek иногда переносит цвет между сегментами («§7Даёт владельцу эффект
    §bСвободы» вместо «§7… §b… §7…») или добавляет завершающий §-код. Это не
    ломает отрисовку, поэтому такие переводы берём, а не отбрасываем.
    """
    if not ru or not ru.strip():
        return False
    if "[[" in ru or "]]" in ru or re.search(r"\{\d+\}", ru):
        return False
    if ru.strip() == src.strip():
        return False
    sc = CODE_RE.findall(src)
    rc = CODE_RE.findall(ru)
    if sc == rc:
        return True
    # лишние коды допустимы только в конце строки
    extra = 0
    while extra < len(rc) and rc[len(rc) - 1 - extra] not in sc:
        extra += 1
    return _subseq(rc[:len(rc) - extra], sc)


def main() -> int:
    src = json.loads((WORK / "ui_strings.json").read_text(encoding="utf-8"))
    deepl_map = json.loads((WORK / "ui_strings_ru_deepl.json").read_text(encoding="utf-8"))
    terms = json.loads((WORK / "terms_mined.json").read_text(encoding="utf-8"))

    masker = BrandMasker(build_brands())

    # восстанавливаем маску брендов: ключ кэша — маскированная строка + подсказки
    cache: dict[str, str] = {}
    for p in sorted(WORK.glob("cache_deepseek_ui*.json")):
        name = p.name
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            print(f"{name}: {len(data)} записей")
            cache.update(data)

    # ключ кэша: masked + "\x00" + json(terms)
    from translate_ui_deepseek import hints_for, term_index
    idx = term_index(terms)

    result: dict[str, str] = {}
    stats = {"deepseek": 0, "deepl": 0, "нет": 0}
    for s in src:
        masked, found = masker.mask(s)
        h = hints_for(s, terms, idx)
        key = masked + "\x00" + json.dumps(h, ensure_ascii=False, sort_keys=True)
        ru = cache.get(key)
        if ru:
            ru = masker.unmask(ru, found)
        if ru and validate_codes(s, ru):
            result[s] = ru
            stats["deepseek"] += 1
            continue
        alt = deepl_map.get(s)
        if alt and validate(s, alt):
            result[s] = alt
            stats["deepl"] += 1
        else:
            stats["нет"] += 1
            if alt:
                result[s] = alt

    (WORK / "ui_strings_ru.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    cyr = sum(1 for v in result.values() if re.search(r"[а-яёА-ЯЁ]", v))
    print(f"\nсловарь: {len(result)} строк (из {len(src)})")
    print(f"  DeepSeek: {stats['deepseek']}, запасной DeepL: {stats['deepl']}, "
          f"без перевода: {stats['нет']}")
    print(f"  с кириллицей: {cyr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
