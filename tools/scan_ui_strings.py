"""Точный поиск английских строк, которые реально попадают в тултипы.

Идея: строка из константного пула сама по себе ничего не значит (их десятки
тысяч: логи, сообщения об ошибках, метаданные). Но класс, который ссылается
на API тултипов (appendHoverText, getTooltipLines, TooltipComponent,
showTooltip …), почти наверняка формирует текст для игрока.

Поэтому: сначала находим «тултипные» классы, потом собираем кандидатов
только из них.

Результат: work/ui_strings.json = {строка: ["jar|class", ...]}
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODS = HERE.parent / "mods"
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from classfile import ClassFile  # noqa: E402

WORD = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CODE = re.compile(r"§[0-9a-fk-orA-FK-OR]")

# признаки класса, который работает с подсказками
TOOLTIP_MARKERS = (
    "appendHoverText", "getTooltipLines", "TooltipComponent", "showTooltip",
    "appendTooltip", "Tooltip", "tooltip", "TOOLTIP",
)

COMMON = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "with", "for",
    "from", "by", "is", "are", "be", "that", "this", "it", "as", "at", "you",
    "your", "when", "while", "can", "will", "not", "all", "each", "into",
    "deals", "deal", "damage", "health", "gives", "grants", "increases",
    "reduces", "chance", "level", "levels", "block", "blocks", "item", "items",
    "player", "players", "target", "targets", "effect", "effects", "ability",
    "abilities", "bonus", "additional", "more", "less", "stack", "stacks",
    "seconds", "second", "minute", "minutes", "ticks", "tick", "s",
}


def looks_like_text(s: str) -> bool:
    if not s or len(s) < 6 or len(s) > 240:
        return False
    if CTRL.search(s):
        return False
    body = CODE.sub("", s).strip()
    if not body or not body.isascii():
        return False
    # служебные знаки — форматирование, идентификаторы, пути.
    # Скобки [ ] разрешены: «[Blood Drain]» — обычная часть тултипа.
    if re.search(r"[/\\{}<>|=+*@~^`$]", s):
        return False
    if re.search(r"[a-z]{2,}[._][a-z]{2,}", body):
        return False
    # resource-id вида "minecraft:stone" — не пользовательский текст
    if re.search(r"\b[a-z][a-z0-9_]*:[a-z0-9_./]+\b", body):
        return False
    if " " not in body:
        return False
    words = WORD.findall(body)
    if len(words) < 2:
        return False
    camel = sum(1 for w in words if re.match(r"^[A-Z][a-z]+[A-Z]", w))
    if camel >= 2:
        return False
    if not any(w[:1].isupper() for w in words) and not any(w.lower() in COMMON for w in words):
        return False
    if len(words) > 40:
        return False
    return True


def main() -> int:
    found: dict[str, list[str]] = {}
    classes = 0
    tooltip_classes = 0
    # для пропатченных jar-ов берём оригиналы из бэкапа, иначе строки
    # уже переведены и повторный скан их не найдёт
    backup = HERE / "backup" / "jars_original"
    for jar in sorted(MODS.glob("*.jar")):
        src = backup / jar.name
        path = src if src.exists() else jar
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            continue
        for name in z.namelist():
            if not name.endswith(".class"):
                continue
            try:
                cf = ClassFile(z.read(name))
            except Exception:
                continue
            classes += 1
            strings = cf.utf8_strings()
            blob = "\n".join(strings)
            is_tooltip_class = any(m in blob for m in TOOLTIP_MARKERS)
            if is_tooltip_class:
                tooltip_classes += 1
            for s in strings:
                # §-коды — верный признак игрового текста, такой класс берём целиком;
                # без §-кодов берём только классы, работающие с подсказками
                if not (is_tooltip_class or "§" in s):
                    continue
                if looks_like_text(s):
                    found.setdefault(s, []).append(f"{jar.name}|{name}")
        z.close()

    out = {s: sorted(set(locs)) for s, locs in sorted(found.items())}
    (WORK / "ui_strings.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    per_mod: dict[str, int] = {}
    for locs in out.values():
        for loc in locs:
            jar = loc.split("|")[0]
            per_mod[jar] = per_mod.get(jar, 0) + 1
    print(f"классов: {classes}, из них тултипных: {tooltip_classes}")
    print(f"уникальных строк: {len(out)}, модов затронуто: {len(per_mod)}")
    print("\nпо модам (топ-30):")
    for jar, cnt in sorted(per_mod.items(), key=lambda kv: -kv[1])[:30]:
        print(f"  {cnt:5d}  {jar[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
