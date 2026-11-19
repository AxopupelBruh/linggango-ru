"""Собирает пользовательский текст из конфигов сборки (меню, подсказки, сложности).

Источники:
  1. config/class_enhancement/classes/*.json  — экран выбора класса (name/description/stats/skill/passives)
  2. config/tips_enhancement-client.toml        — подсказки и гайды (tipsList)
  3. config/difficulty_enhancement-common.toml  — названия и описания сложностей
  4. config/linggango_machinery/**.json         — названия контроллеров и портов
  5. config/warningscreen.json                  — экран предупреждения при запуске
  6. config/crash_assistant/config.toml         — тексты, перекрывающие перевод мода

Файлы:
  work/extra.json      = {текст: [индексы элементов]}  — для run.py
  work/extra_items.json= [элементы]                   — план применения
"""
import json
import re
import tomllib
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

ROOT = INSTANCE
HERE = Path(__file__).parent
WORK = HERE / "work"

# Похоже на lang-ключ ("class.linggango.class_enhancement.ranger.name") — переводить нельзя
RE_LANG_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
RE_COLOR_PREFIX = re.compile(r"^(&[0-9a-zA-Z])?(.*)$", re.S)

# Ярлыки подсказок переводим вручную — это служебные метки, а не проза
TIP_LABELS = {
    "Tips": "Подсказки",
    "Guide": "Гайд",
    "Did you know?": "А вы знали?",
}

items: list[dict] = []


def add(kind: str, file: str, text: str, **kw) -> None:
    text = text.strip()
    if not text:
        return
    if RE_LANG_KEY.match(text):
        return
    items.append({"kind": kind, "file": file, "text": text, **kw})


# ---------------------------------------------------------------------------
# 1. Классы
# ---------------------------------------------------------------------------

def collect_classes() -> None:
    base = ROOT / "config/class_enhancement/classes"
    for f in sorted(base.glob("*.json")):
        rel = f"config/class_enhancement/classes/{f.name}"
        data = json.loads(f.read_text(encoding="utf-8"))
        add("json", rel, data.get("name", ""), path=["name"])
        add("json", rel, data.get("description", ""), path=["description"])
        for i, s in enumerate(data.get("stats") or []):
            add("json", rel, s, path=["stats", i])
        skill = data.get("skill")
        if isinstance(skill, dict):
            add("json", rel, skill.get("name", ""), path=["skill", "name"])
            add("json", rel, skill.get("description", ""), path=["skill", "description"])
        for i, p in enumerate(data.get("passives") or []):
            if not isinstance(p, dict):
                continue
            add("json", rel, p.get("name", ""), path=["passives", i, "name"])
            add("json", rel, p.get("description", ""), path=["passives", i, "description"])


# ---------------------------------------------------------------------------
# 2. Подсказки
# ---------------------------------------------------------------------------

def collect_tips() -> None:
    rel = "config/tips_enhancement-client.toml"
    f = ROOT / rel
    raw = f.read_text(encoding="utf-8")
    m = re.search(r"^\s*tipsList\s*=\s*(\[.*\])\s*$", raw, re.M)
    if not m:
        return
    tips = json.loads(m.group(1))
    for i, tip in enumerate(tips):
        mm = RE_COLOR_PREFIX.match(tip)
        prefix = mm.group(1) or ""
        rest = mm.group(2)
        if "|" in rest:
            label, body = rest.split("|", 1)
            add("tip", rel, body, index=i, prefix=prefix, label=label)
        else:
            add("tip", rel, rest, index=i, prefix=prefix, label=None)
    m2 = re.search(r'^\s*defaultTipTitle\s*=\s*"([^"]*)"', raw, re.M)
    if m2:
        # заголовок окна подсказок — фиксированная замена, "&l&n" трогать нельзя
        items.append({"kind": "fixed", "file": rel, "text": m2.group(1),
                      "ru": "&l&nПодсказки", "key": "defaultTipTitle"})


# ---------------------------------------------------------------------------
# 3. Сложности
# ---------------------------------------------------------------------------

def collect_difficulty() -> None:
    rel = "config/difficulty_enhancement-common.toml"
    f = ROOT / rel
    data = tomllib.loads(f.read_text(encoding="utf-8"))
    for key in ("name", "recommendation"):
        if key in data:
            add("toml", rel, data[key], path=[key])
    for table, val in data.items():
        if not isinstance(val, dict):
            continue
        if table in ("general", "mechanics"):
            continue
        for key in ("name", "recommendation"):
            if isinstance(val.get(key), str) and val[key].strip():
                add("toml", rel, val[key], path=[table, key])
    cd = data.get("custom_difficulties")
    if isinstance(cd, dict):
        for name, val in cd.items():
            if not isinstance(val, dict):
                continue
            for key in ("name", "description"):
                if isinstance(val.get(key), str) and val[key].strip():
                    add("toml", rel, val[key], path=["custom_difficulties", name, key])


# ---------------------------------------------------------------------------
# 4. Механизмы
# ---------------------------------------------------------------------------

def collect_machinery() -> None:
    base = ROOT / "config/linggango_machinery"
    for sub in ("controllers", "ports"):
        for f in sorted((base / sub).glob("*.json")):
            rel = f"config/linggango_machinery/{sub}/{f.name}"
            data = json.loads(f.read_text(encoding="utf-8"))
            add("json", rel, data.get("name", ""), path=["name"])


# ---------------------------------------------------------------------------
# 5. Экран предупреждения
# ---------------------------------------------------------------------------

def collect_warning() -> None:
    rel = "config/warningscreen.json"
    f = ROOT / rel
    data = json.loads(f.read_text(encoding="utf-8"))
    for i, w in enumerate(data.get("warnings") or []):
        for key in ("title", "warning", "smallText"):
            add("json", rel, w.get(key, ""), path=["warnings", i, key])


# ---------------------------------------------------------------------------
# 6. Crash Assistant (тексты, перекрывающие перевод мода)
# ---------------------------------------------------------------------------

def collect_crash() -> None:
    rel = "config/crash_assistant/config.toml"
    f = ROOT / rel
    data = tomllib.loads(f.read_text(encoding="utf-8"))
    text = data.get("text") or {}
    if isinstance(text.get("support_name"), str):
        add("toml", rel, text["support_name"], path=["text", "support_name"])
    gm = data.get("generated_message") or {}
    if isinstance(gm.get("text_under_crashed"), str):
        add("toml", rel, gm["text_under_crashed"], path=["generated_message", "text_under_crashed"])


def main() -> None:
    WORK.mkdir(exist_ok=True)
    items.clear()
    collect_classes()
    collect_tips()
    collect_difficulty()
    collect_machinery()
    collect_warning()
    collect_crash()

    index: dict[str, list[int]] = {}
    for i, it in enumerate(items):
        index.setdefault(it["text"], []).append(i)

    (WORK / "extra_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "extra.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    chars = sum(len(t) for t in index)
    print(f"extra      {len(index):7,} уникальных строк  {chars:9,} символов  "
          f"({len(items)} мест)")


if __name__ == "__main__":
    main()
