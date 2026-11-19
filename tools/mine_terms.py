"""Автоматический майнинг терминов из уже готовых переводов.

Идея: в lang-файлах модов строка вида
    §e -Grants §cLife Steal §efor 25 seconds
    §e - Даёт §cпохищение жизни §eна 25 секунд
разбивается по §-кодам на параллельные куски. Сопоставляя куски, получаем
термин → перевод: «Life Steal» → «похищение жизни».

Так термины в зашитых в код тултипах совпадают с терминами в lang-файлах,
и DeepL не выдумывает свои варианты.

Результат: work/terms_mined.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

CODE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9' ]*")


def segments(text: str) -> list[tuple[str, str]]:
    """[(коды перед куском, текст куска)] — куски разделены §-кодами."""
    out: list[tuple[str, str]] = []
    codes: list[str] = []
    pos = 0
    for m in CODE.finditer(text):
        chunk = text[pos:m.start()]
        out.append(("".join(codes), chunk))
        codes = [m.group(0)]
        pos = m.end()
    out.append(("".join(codes), text[pos:]))
    return out


def main() -> int:
    mods_ru = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    terms: dict[str, str] = {}
    votes: dict[str, dict[str, int]] = {}

    for en, ru in mods_ru.items():
        if not isinstance(ru, str) or not isinstance(en, str):
            continue
        if not CODE.sub("", en).isascii():
            continue
        se, sr = segments(en), segments(ru)
        if len(se) != len(sr):
            continue
        for (_ce, te), (_cr, tr) in zip(se, sr):
            te = te.strip()
            tr = tr.strip()
            if not te or not tr:
                continue
            # убираем хвостовую пунктуацию: «Passive Effect:» → «Passive Effect»
            term = te.rstrip(":,.;")
            if not term or term != te.rstrip(":,.;!"):
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9'’\- ]*", term):
                continue
            if len(term.split()) > 3:
                continue
            if not re.search(r"[а-яё]", tr):
                continue
            if not term[:1].isupper():
                continue
            # перевод не должен заканчиваться висячей пунктуацией
            if re.search(r"[.,;:]$", tr):
                tr = tr.rstrip(".,;:")
            votes.setdefault(term, {})
            votes[term][tr] = votes[term].get(tr, 0) + 1

    # берём самый частый вариант перевода
    for term, variants in votes.items():
        best = max(variants.items(), key=lambda kv: kv[1])[0]
        terms[term] = best

    # однословные термины часто — обычные слова («Provides», «Default»):
    # оставляем только те, что встречаются много раз (устойчивые термины)
    stable = {t: v for t, v in terms.items()
              if " " in t or sum(votes[t].values()) >= 3}

    (WORK / "terms_mined.json").write_text(
        json.dumps(stable, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"терминов всего: {len(terms)}, устойчивых (используем): {len(stable)}")
    for t in ["Invisibility", "Life Steal", "Shadowflame", "Haste", "Speed",
              "Passive Effect", "Dash Ability", "Default Keybind"]:
        print(f"   {t!r} -> {stable.get(t)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
