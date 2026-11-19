"""Починка терминологии после перевода (с учётом падежей).

Зачем: DeepL переводит грамматически правильно, но названия модов и предметов
у него часто свои («Warden» → «надзиратель», хотя в игре — «Хранитель»).
Схема:
  1. термин переводится отдельно -> получаем, как DeepL его называет;
  2. строим таблицу падежных форм и для перевода DeepL, и для канона;
  3. в предложении заменяем форму DeepL на соответствующую форму канона
     («надзирателя» -> «Хранителя»), сохраняя регистр.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent

# падежные окончания по роду и числу
FORMS = {
    "m": [("nom", ""), ("gen", "а"), ("dat", "у"), ("acc", "а"), ("ins", "ом"), ("pre", "е")],
    "f_soft": [("nom", ""), ("gen", "и"), ("dat", "и"), ("acc", "ь"), ("ins", "ью"), ("pre", "и")],
    "f": [("nom", ""), ("gen", "ы"), ("dat", "е"), ("acc", "у"), ("ins", "ой"), ("pre", "е")],
    "n": [("nom", ""), ("gen", "а"), ("dat", "у"), ("acc", "а"), ("ins", "ом"), ("pre", "е")],
}


def gender(word: str) -> str:
    w = word.strip().lower()
    if w.endswith(("ь", "ъ")):
        return "f_soft"
    if w.endswith(("а", "я")):
        return "f"
    if w.endswith(("о", "е")):
        return "n"
    return "m"


def case_forms(word: str) -> dict[str, str]:
    """Падежные формы одного слова: {case: форма}."""
    stem = word.strip()
    if not stem:
        return {}
    g = gender(stem)
    out = {}
    for case, suf in FORMS[g]:
        out[case] = stem + suf
    # множественное число
    pl_stem = stem
    if g == "m":
        pl_stem = stem + "и"
        out["pl_nom"] = pl_stem
        out["pl_gen"] = pl_stem + "х" if stem.endswith(("к", "г", "х", "ж", "ч", "ш")) else pl_stem + "ев"
        out["pl_dat"] = pl_stem + "м"
        out["pl_acc"] = pl_stem + "х" if stem.endswith(("к", "г", "х", "ж", "ч", "ш")) else pl_stem + "ев"
        out["pl_pre"] = pl_stem + "х" if stem.endswith(("к", "г", "х", "ж", "ч", "ш")) else pl_stem + "ах"
    else:
        out["pl_nom"] = stem + "ы" if g in ("f", "f_soft") else stem + "и"
        out["pl_gen"] = stem + "ов"
        out["pl_dat"] = stem + "ам"
        out["pl_acc"] = stem + "ов"
        out["pl_pre"] = stem + "ах"
    # мягкий знак перед гласной
    fixed = {}
    for case, form in out.items():
        fixed[case] = form
        if form.endswith(("а", "у", "ю", "я")) and not form.endswith("ь"):
            fixed[case + "_soft"] = form[:-1] + "ь" + form[-1]
    return fixed


def split_name(word: str) -> tuple[str, str]:
    """Многословные названия склоняются в первом слове."""
    parts = word.strip().split(" ", 1)
    if len(parts) == 1:
        return word.strip(), ""
    return parts[0], " " + parts[1]


def case_pairs(deepl: str, canonical: str) -> list[tuple[str, str]]:
    """Пары (форма DeepL -> форма канона) для каждого падежа."""
    d_head, d_tail = split_name(deepl)
    c_head, c_tail = split_name(canonical)
    d_forms = case_forms(d_head)
    c_forms = case_forms(c_head)
    pairs = []
    for case, d_form in d_forms.items():
        base_case = case.replace("_soft", "")
        c_form = c_forms.get(base_case) or c_forms.get(case)
        if not c_form:
            continue
        pairs.append((d_form + d_tail, c_form + c_tail))
    # исходная форма
    pairs.append((deepl.strip(), canonical.strip()))
    return pairs


class TermFixer:
    """Заменяет переводы терминов на канонические (с учётом падежа)."""

    MIN_LEN = 4

    def __init__(self, glossary: dict, term_map: dict):
        self.entries = []
        for en, info in term_map.items():
            canonical = (info.get("ru") or "").strip()
            deepl = (info.get("deepl") or "").strip()
            if not canonical or not deepl:
                continue
            if canonical.lower() == deepl.lower():
                continue
            self.entries.append((en.lower(), canonical, deepl))
        self.entries.sort(key=lambda e: -len(e[0]))

    @staticmethod
    def _match_case(model: str, replacement: str) -> str:
        if model[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement[:1].lower() + replacement[1:]

    def fix(self, src_en: str, ru_text: str) -> str:
        if not self.entries or not ru_text:
            return ru_text
        low = src_en.lower()
        for en_term, canonical, deepl in self.entries:
            if en_term not in low:
                continue
            for from_form, to_form in case_pairs(deepl, canonical):
                if len(from_form) < self.MIN_LEN:
                    continue
                pattern = re.compile(
                    r"(?<![0-9A-Za-zЀ-ӿ])" + re.escape(from_form) + r"(?![0-9A-Za-zЀ-ӿ])",
                    re.IGNORECASE)
                if pattern.search(ru_text):
                    ru_text = pattern.sub(
                        lambda m: self._match_case(m.group(0), to_form), ru_text)
        return ru_text


def load_term_map(path: Path | None = None) -> dict:
    p = path or (HERE / "term_map.json")
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
