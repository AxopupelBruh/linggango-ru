"""Бренды модов, которые нельзя переводить/транслитерировать.

Используется fix_translate.py (после перевода LLM) и audit_case.py (починка
уже готовых переводов). Логика: если в английском оригинале бренд стоит как
ИМЯ СОБСТВЕННОЕ, а в переводе — его транслитерация, возвращаем латиницу.

Важно:
  * сравнение только по целым словам («Создайте» ≠ «Создать»);
  * бренд считается именем собственным, если в оригинале он с большой буквы
    и не является глаголом-словарным словом («Create a space suit» — это глагол,
    а не мод Create);
  * спорные бренды (Create, Jade) не восстанавливаются автоматически: модель
    о них знает из системного промпта, а автоматическая замена портит обычные
    предложения («Создайте скафандр» → «Createте скафандр»).
"""

from __future__ import annotations

import re

# Латинское имя бренда -> варианты транслитерации в русском
BRAND_RU: dict[str, tuple[str, ...]] = {
    "FTB": ("ФТБ", "Фтб"),
    "JEI": ("ДЖЭИ", "ДЖЕИ", "Джеи", "ДЖей"),
    "REI": ("РЕЙ", "Рей", "Реи"),
    "WTHIT": ("ВТХИТ", "Втхит"),
    "Mekanism": ("Меканизм", "Меканизма"),
    "Ars Nouveau": ("Арс Нуво",),
    "Patchouli": ("Патчули",),
    "Occultism": ("Оккультизм",),
    "Ad Astra": ("Ад Астра",),
    "Sophisticated Storage": ("Софистикейтед Сторедж",),
    "Immersive Engineering": ("Иммерсив Инжиниринг",),
    "Curios": ("Куриос",),
    "Botania": ("Ботания",),
    "Xaero's": ("Ксеро",),
}

# слова, после которых бренд — это глагол, а не имя мода
_VERB_CONTEXT = re.compile(
    r"\b(create|creating|created|use|using|used|open|opening|place|placing|"
    r"break|breaking|get|getting|make|making|craft|crafting|hold|holding)\b",
    re.IGNORECASE)

_BRAND_RE = {b: re.compile(rf"(?<![\w]){re.escape(b)}(?![\w])") for b in BRAND_RU}
_VARIANT_RE = {
    b: [re.compile(rf"(?<![\w]){re.escape(v)}(?![\w])") for v in variants]
    for b, variants in BRAND_RU.items()
}


def brand_is_name(en: str, brand: str) -> bool:
    """Бренд в оригинале используется как имя собственное (а не как глагол)."""
    m = _BRAND_RE[brand].search(en or "")
    if not m:
        return False
    if brand == "Create":
        return False
    tail = (en or "")[m.end():]
    if _VERB_CONTEXT.match(tail.strip()):
        return False
    return True


def restore_brands(en: str, ru: str) -> str:
    """Возвращает латинское написание бренда, если в оригинале он был именем."""
    if not ru:
        return ru
    for brand, patterns in _VARIANT_RE.items():
        if not brand_is_name(en, brand):
            continue
        for rx in patterns:
            ru = rx.sub(brand, ru)
    return ru


def contains_brand(en: str) -> bool:
    return any(rx.search(en or "") for rx in _BRAND_RE.values())
