"""Восстанавливает разметку квестов, которую переводчик испортил.

Что ломалось:
  * `[gap=5]`   → `[пробел=5]`   — игра перестаёт понимать отступ,
  * `[!danger]` → `[!опасность]` — ломается выноска,
  * `[spoiler]` → `[спойлер]`,
  * `{image:customtextures:textures/x.png …}` → `…:текстуры/x.png …` —
    из-за этого мод кидает ResourceLocationException.

Разметка восстанавливается по позициям: маркеры в оригинале и в переводе
идут в одном порядке, поэтому достаточно подставить оригинальный токен.
Строки, где порядок разъехался, попадают в отчёт.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
sys.path.insert(0, str(HERE))
from tr_engine import RE_MARKUP  # noqa: E402

# любой «скобочный» токен: {image:…} или [что-то]
TOKEN = re.compile(r"\{image:[^}]*\}|\[[^\[\]]{0,160}\]")


def main() -> None:
    path = WORK / "quests_ru.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fixed = 0
    skipped: list[tuple[str, str]] = []

    for src in list(data):
        ru = data[src]
        if src == ru:
            continue
        s_mark = set(RE_MARKUP.findall(src))
        if not s_mark:
            continue
        s_all = TOKEN.findall(src)
        r_all = TOKEN.findall(ru)
        if len(s_all) != len(r_all):
            skipped.append((src[:90], f"токенов {len(s_all)}→{len(r_all)}"))
            continue
        # восстанавливаем по позициям
        out = []
        pos = 0
        for i, (st, rt) in enumerate(zip(s_all, r_all)):
            idx = ru.find(rt, pos)
            if idx < 0:
                skipped.append((src[:90], "токен не найден"))
                out = []
                break
            out.append(ru[pos:idx])
            if st in s_mark:
                out.append(st)          # разметка — возвращаем как была
                fixed += 1
            else:
                out.append(rt)          # обычный текст в скобках — оставляем перевод
            pos = idx + len(rt)
        if not out:
            continue
        out.append(ru[pos:])
        new = "".join(out)
        if new != ru:
            data[src] = new

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"маркеров восстановлено: {fixed}")
    print(f"строк с расхождением: {len(skipped)}")
    for s, why in skipped[:20]:
        print(f"   {why}: {s!r}")


if __name__ == "__main__":
    main()
