"""Собирает ресурспак zz_linggango_ru с переводами модов и Patchouli-книг.

Структура:
  assets/<namespace>/lang/ru_ru.json                      — переводы интерфейса и имён
  assets/<namespace>/patchouli_books/<book>/ru_ru/...    — страницы книг
  pack.mcmeta

Ресурспак не трогает jar-файлы: переживает обновление сборки через CurseForge.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE, WORK_DIR  # noqa: E402
from brands import restore_brands  # noqa: E402
from lang_json import load_lang_json  # noqa: E402

HERE = Path(__file__).parent
ROOT = INSTANCE
MODS = ROOT / "mods"
WORK = HERE / "work"
PACK_NAME = "zz_linggango_ru"


def load_ru(source: str) -> dict[str, str]:
    p = WORK / f"{source}_ru.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


# ведущая разметка (§-коды, теги, пробелы) — её пропускаем, сравнивая первые буквы
LEAD = re.compile(r"^(\s*(?:[§&][0-9a-fk-orA-FK-OR]|\[[^\]]{0,40}\]|<[^>]{0,40}>)*)")
CYR = re.compile(r"[а-яёА-ЯЁ]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def _first_letter(text: str) -> str:
    """Первая буква слова без учёта ведущих кодов цвета и разметки."""
    m = LEAD.match(text)
    rest = text[m.end():] if m else text
    fm = LETTER.search(rest)
    return fm.group(0) if fm else ""


def fix_start_case(en: str, ru: str) -> str:
    """Поднимает первую букву перевода, если в оригинале она заглавная."""
    if not ru or not ru.strip():
        return ru
    fe, fr = _first_letter(en), _first_letter(ru)
    if not fe or not fr:
        return ru
    if not (fe.isupper() and fr.islower()):
        return ru
    m = LEAD.match(ru)
    lead = m.group(1) if m else ""
    rest = ru[len(lead):]
    cm = CYR.search(rest)
    if not cm:
        return ru
    i = cm.start()
    prefix = rest[:i]
    # не капитализируем, если впереди плейсхолдер или число
    if re.search(r"%[-+0-9.#]*[a-zA-Z]|\{\d+\}|\{|\d", prefix):
        return ru
    return lead + rest[:i] + rest[i].upper() + rest[i + 1:]


def build_lang_files(out: Path, translations: dict[str, str]) -> tuple[int, int]:
    """Пишет assets/<ns>/lang/ru_ru.json.

    ВАЖНО: в Minecraft файл языка ресурспака ЗАМЕНЯЕТ файл мода целиком
    (а не дополняет его). Поэтому мы обязаны писать полный объединённый файл:
    сначала чужие переводы мода, поверх — наши правки.
    """
    en_by_ns: dict[str, dict[str, str]] = defaultdict(dict)
    ru_by_ns: dict[str, dict[str, str]] = defaultdict(dict)
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if "/lang/" not in name:
                continue
            folder, fname = name.rsplit("/", 1)
            if fname not in ("en_us.json", "ru_ru.json"):
                continue
            try:
                data = load_lang_json(z.read(name))
            except Exception:
                continue
            ns = folder.split("/")[1]
            (en_by_ns if fname == "en_us.json" else ru_by_ns)[ns].update(data)

    files = 0
    keys = 0
    # Ванильный ru_ru: lang-файл ресурспака ЗАМЕНЯЕТ файл клиента целиком.
    # Если приложить свой assets/minecraft/lang/ru_ru.json с парой ключей,
    # весь ванильный интерфейс откатится на английский. Поэтому берём
    # официальный ванильный русский и добавляем к нему наши правки.
    vanilla_ru = {}
    vpath = WORK / "vanilla_ru_ru.json"
    if vpath.exists():
        vanilla_ru = json.loads(vpath.read_text(encoding="utf-8"))
        print(f"ванильный ru_ru: {len(vanilla_ru)} ключей")

    for ns, en in en_by_ns.items():
        existing = ru_by_ns.get(ns, {})
        # объединённый файл: чужие переводы сохраняем, наши — поверх
        merged = dict(existing)
        changed = 0
        for key, val in en.items():
            if not isinstance(val, str):
                continue
            cur = existing.get(key)
            ru = translations.get(val)
            if cur is not None and not cur.strip() and val.strip():
                # мод отдал ПУСТОЙ перевод при непустом английском — в игре строка пустая.
                # Перекрываем нашим переводом.
                if ru and ru.strip():
                    merged[key] = ru
                    changed += 1
                continue
            if cur is None:
                # у мода нет своего перевода — берём наш
                if ru and ru.strip():
                    merged[key] = ru
                    changed += 1
                continue
            if cur == val:
                # мод приложил ru_ru.json, но там английский текст —
                # перекрываем нашим переводом (иначе в игре остаётся английский)
                if ru and ru.strip():
                    merged[key] = ru
                    changed += 1
                continue
            # у мода есть собственный перевод — не трогаем его, кроме регистра
            # и транслитераций брендов (ФТБ → FTB, ДЖЭИ → JEI и т.п.)
            fixed = fix_start_case(val, cur)
            fixed = restore_brands(val, fixed)
            if fixed != cur:
                merged[key] = fixed
                changed += 1
        if ns == "minecraft" and vanilla_ru:
            # наш файл заменяет ванильный — кладём туда полный русский
            base = dict(vanilla_ru)
            base.update(merged)
            if base != merged:
                changed += len(base) - len(merged)
            merged = base
        if not changed:
            continue
        path = out / "assets" / ns / "lang" / "ru_ru.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
        files += 1
        keys += changed
    return files, keys


TEXT_FIELDS = ("text", "title", "description", "subtitle", "header", "footer", "name", "heading")

# метка ссылки внутри текста: $(l:ns:path)Метка$(/l), $(item)Метка$()
# ВАЖНО: закрывающий макрос должен идти сразу за меткой, иначе регулярка
# склеит соседние макросы ($(k:use) ... $(item)X$()) и потеряет метку.
LBL_OPEN = r"\$\((?:l|item|entity|t|c|hover|key|lang)(?:[:/][^)]*)?\)"
LBL_CLOSE = r"\$\((?:/l)?\)"
LBL_RE = re.compile(f"({LBL_OPEN})([^$]*?)({LBL_CLOSE})")


def apply_labels(text: str, labels: dict[str, str]) -> str:
    """Подставляет переводы меток ссылок внутри строки книги."""
    if not labels:
        return text

    # целиком английская строка (например заголовок страницы) — заменяем целиком
    whole = text.strip()
    if whole and whole in labels:
        return labels[whole]

    if "$(" not in text:
        return text

    def repl(m: re.Match) -> str:
        lab = m.group(2)
        tr = labels.get(lab.strip())
        if not tr:
            return m.group(0)
        return m.group(1) + tr + m.group(3)

    return LBL_RE.sub(repl, text)


def build_patchouli(out: Path, translations: dict[str, str],
                    labels: dict[str, str] | None = None) -> tuple[int, int]:
    """Переносит en_us-страницы книг в ru_ru с переводом текстовых полей."""
    labels = labels or {}
    books = 0
    fields = 0
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        # какие книги уже имеют ru_ru — их не трогаем
        has_ru = set()
        for name in z.namelist():
            if "patchouli_books" not in name:
                continue
            parts = name.split("/")
            if "patchouli_books" not in parts:
                continue
            i = parts.index("patchouli_books")
            if len(parts) > i + 2 and parts[i + 2] == "ru_ru":
                has_ru.add((parts[i - 1], parts[i + 1]))
        for name in z.namelist():
            if "patchouli_books" not in name or not name.endswith(".json"):
                continue
            parts = name.split("/")
            try:
                i = parts.index("patchouli_books")
            except ValueError:
                continue
            if len(parts) <= i + 2 or parts[i + 2] != "en_us":
                continue
            ns, book = parts[i - 1], parts[i + 1]
            if (ns, book) in has_ru:
                continue
            try:
                data = load_lang_json(z.read(name))
            except Exception:
                continue

            def walk(node):
                nonlocal fields
                if isinstance(node, dict):
                    for k, v in node.items():
                        if k in TEXT_FIELDS and isinstance(v, str):
                            ru = translations.get(v)
                            if ru and ru.strip():
                                node[k] = apply_labels(ru, labels)
                                fields += 1
                            else:
                                node[k] = apply_labels(v, labels)
                        elif isinstance(v, str):
                            node[k] = apply_labels(v, labels)
                        else:
                            walk(v)
                elif isinstance(node, list):
                    for i, v in enumerate(node):
                        if isinstance(v, str):
                            node[i] = apply_labels(v, labels)
                        else:
                            walk(v)

            walk(data)
            rel = Path(*parts[i + 3:]) if len(parts) > i + 3 else Path(name.split("/")[-1])
            target = out / "assets" / ns / "patchouli_books" / book / "ru_ru" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            books += 1
    return books, fields


def write_pack_mcmeta(out: Path) -> None:
    (out / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "pack_format": 15,
            "description": "Linggango — русская локализация (переводы модов, книг и интерфейса)",
        }
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def zip_pack(folder: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(folder))


def main():
    stage = HERE / "pack_build"
    if stage.exists():
        import shutil
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    mod_ru = load_ru("mods")
    files, keys = build_lang_files(stage, mod_ru)
    print(f"lang-файлов: {files}, ключей: {keys}")

    po_ru = load_ru("patchouli")
    labels = {}
    lbl_path = WORK / "patchouli_labels_ru.json"
    if lbl_path.exists():
        labels = json.loads(lbl_path.read_text(encoding="utf-8"))
    books, fields = build_patchouli(stage, po_ru, labels)
    print(f"книг: {books}, переведённых полей: {fields}, меток ссылок: {len(labels)}")

    write_pack_mcmeta(stage)

    # Дополнительные ключи, которых нет ни в одном моде (картины без lang,
    # «сырые» rarity.*, зачарования без перевода). Кладём в отдельный
    # namespace: lang-ключи в Minecraft глобальные, поэтому файл не задевает
    # переводы модов, но закрывает недостающие строки.
    extra_path = WORK / "lang_extra.json"
    if extra_path.exists():
        extra = json.loads(extra_path.read_text(encoding="utf-8"))
        if extra:
            p = stage / "assets" / "linggango_ru" / "lang" / "ru_ru.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(extra, ensure_ascii=False, indent=1),
                         encoding="utf-8")
            print(f"доп. ключей: {len(extra)} (assets/linggango_ru/lang/ru_ru.json)")

    zip_path = ROOT / "resourcepacks" / f"{PACK_NAME}.zip"
    zip_pack(stage, zip_path)
    print(f"ресурспак: {zip_path} ({zip_path.stat().st_size // 1024} КБ)")

    # регистрируем пак в конфиге сборки (последним = высший приоритет) и в options.txt
    toml = ROOT / "config/linggango-resourcepacks.toml"
    text = toml.read_text(encoding="utf-8")
    entry = f'"file/{PACK_NAME}.zip"'
    if entry not in text:
        text = text.replace('packs = [', 'packs = [' + entry + ', ', 1)
        toml.write_text(text, encoding="utf-8")
        print("добавлен в linggango-resourcepacks.toml")

    opts = ROOT / "options.txt"
    otext = opts.read_text(encoding="utf-8")
    if entry not in otext:
        otext = re.sub(r'(resourcePacks:\[)', r'\1' + entry + ',', otext, count=1)
        opts.write_text(otext, encoding="utf-8")
        print("добавлен в options.txt")


if __name__ == "__main__":
    main()
