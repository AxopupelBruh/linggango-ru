"""Собирает ресурспак zz_linggango_ru с переводами модов и Patchouli-книг.

Структура:
  assets/<namespace>/lang/ru_ru.json                      — переводы интерфейса и имён
  assets/<namespace>/patchouli_books/<book>/ru_ru/...    — страницы книг
  pack.mcmeta

Ресурспак не трогает jar-файлы: переживает обновление сборки через CurseForge.
"""
from __future__ import annotations

import json
import difflib
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE, WORK_DIR  # noqa: E402
from brands import restore_brands  # noqa: E402
from lang_json import load_lang_json  # noqa: E402
from lang_sources import (  # noqa: E402
    dir_lang,
    load_mploc_snapshot,
    mod_lang,
    mod_namespaces,
    pack_assets,
    pack_lang,
    save_mploc_snapshot,
)

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


def load_pack_lang(pack_name: str) -> dict[str, dict[str, str]]:
    """Чужие переводы из ресурспака (MPLOCmods) — по неймспейсам.

    Оставлено для разовых запросов; основной сбор идёт через lang_sources.
    """
    return pack_lang(ROOT / "resourcepacks" / pack_name)


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


def placeholder_signature(text: str) -> tuple:
    """Аргументы форматирования и §-коды: их набор менять нельзя."""
    args = sorted(re.findall(r"%(?:\d+\$)?[sdif]", text))
    codes = sorted(re.findall(r"§[0-9a-fk-or]", text))
    return tuple(args), tuple(codes)


# Пространства имён, где мод приложил перевод от старой версии и строки
# съехали по ключам (armageddon_mod: тултипы оружия). Для них сверяем ещё
# числа и римские цифры — иначе в игре «+0.1 Attack Speed» вместо «+0.2».
STRICT_NS = {"armageddon_mod"}
ROMAN = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}


def content_signature(text: str) -> tuple:
    """placeholder_signature + числа и римские цифры (для съехавших переводов)."""
    plain = re.sub(r"§[0-9a-fk-or]", "", text)
    # 7,5 и 7.5 — одно и то же число, просто разный разделитель
    nums = sorted(n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", plain))
    words = (w.strip(".,;:!?()[]{}\"'") for w in plain.split())
    roman = sorted(w for w in words if w in ROMAN)
    return placeholder_signature(text) + (tuple(nums), tuple(roman))


def args_broken(ru: str, en: str) -> bool:
    """Разошлись ли %-аргументы перевода с оригиналом."""
    return placeholder_signature(ru) != placeholder_signature(en)


def pick_from_chain(src: list[dict[str, str]], key: str, en_val: str,
                    skip: str | None = None) -> str | None:
    """Берёт перевод ключа из следующего источника, если текущий битый.

    Источники идут в порядке приоритета; пропускаем уже использованное
    значение, английский текст и переводы с разъехавшимися %-аргументами.
    """
    fallback = None
    for d in src:
        v = d.get(key)
        if not isinstance(v, str) or not v.strip():
            continue
        v = v.strip()
        if skip is not None and v == skip.strip():
            continue
        if en_val and v == en_val.strip():
            continue
        if args_broken(v, en_val):
            continue
        if CYR.search(v):
            return v
        if fallback is None:
            fallback = v
    return fallback


def build_lang_files(out: Path, translations: dict[str, str],
                     stale_fix: dict[str, str] | None = None,
                     polish_fix: dict[str, str] | None = None) -> tuple[int, int]:
    """Пишет assets/<ns>/lang/ru_ru.json.

    ВАЖНО: в Minecraft файл языка ресурспака ЗАМЕНЯЕТ файл мода целиком
    (а не дополняет его). Поэтому мы обязаны писать полный объединённый
    файл: сначала чужие переводы (мод, пак KubeJS, пак serilum, чужие
    локализации), поверх — наши правки. Иначе уберём чужой пак из списка —
    и часть переводов пропадёт, игрок снова увидит английский.
    """
    en_by_ns, ru_by_ns = mod_lang(MODS)
    build_ns = mod_namespaces(MODS)

    kubejs_ru = dir_lang(ROOT / "kubejs" / "assets")
    serilum_ru = dir_lang(ROOT / "data" / "serilum" / "translations")

    # Чужие локализации — только для модов, которые есть в сборке.
    # Снимок сохраняем, чтобы сборка не зависела от наличия пака на диске.
    snapshot = WORK / "mploc_ru.json"
    mploc_ru = pack_lang(ROOT / "resourcepacks" / "MPLOCmods.zip",
                         only=build_ns | {"minecraft"})
    if not mploc_ru:
        mploc_ru = load_mploc_snapshot(snapshot)
    if mploc_ru:
        save_mploc_snapshot(snapshot, mploc_ru)
        print(f"чужие переводы (MPLOCmods): {sum(len(v) for v in mploc_ru.values())} ключей "
              f"в {len(mploc_ru)} неймспейсах")

    # Цепочка источников по неймспейсам. Первая годная строка побеждает:
    # перевод мода важнее чужих локализаций, KubeJS и serilum — важнее
    # MPLOCmods (они идут в игре выше по приоритету).
    chain: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ns, d in ru_by_ns.items():
        chain[ns].append(d)
    for ns, d in kubejs_ru.items():
        chain[ns].append(d)
    for ns, d in serilum_ru.items():
        chain[ns].append(d)
    for ns, d in mploc_ru.items():
        chain[ns].append(d)

    # Ванильный ru_ru: lang-файл ресурспака ЗАМЕНЯЕТ файл клиента целиком.
    # Если приложить свой assets/minecraft/lang/ru_ru.json с парой ключей,
    # весь ванильный интерфейс откатится на английский. Поэтому берём
    # официальный ванильный русский и добавляем к нему наши правки.
    vanilla_ru = {}
    vpath = WORK / "vanilla_ru_ru.json"
    if vpath.exists():
        vanilla_ru = json.loads(vpath.read_text(encoding="utf-8"))
        print(f"ванильный ru_ru: {len(vanilla_ru)} ключей")

    # оверрайды по ключу: {"<ns>": {"<key>": "<русский текст>"}}
    key_overrides = {}
    opath = WORK / "key_overrides.json"
    if opath.exists():
        key_overrides = json.loads(opath.read_text(encoding="utf-8"))
        print(f"точечных правок по ключу: {sum(len(v) for v in key_overrides.values())}")

    files = 0
    keys = 0
    for ns in sorted(set(chain) | set(en_by_ns) | {"minecraft"}):
        en = en_by_ns.get(ns, {})
        src = chain.get(ns, [])
        # Объединённый файл: всё, что было видно в игре. Кто первый дал
        # ключ — тот и главный: перевод мода не трогаем без нужды.
        merged: dict[str, str] = {}
        for d in src:
            for k, v in d.items():
                merged.setdefault(k, v)
        changed = 0
        # Файл обязателен, если из него забираем чужие переводы: иначе,
        # убрав чужой пак из списка, мы потеряем эти ключи.
        must_write = ns in mploc_ru
        for key, val in en.items():
            if not isinstance(val, str):
                continue
            ru = translations.get(val)
            cur = merged.get(key)
            if cur is not None and not cur.strip() and val.strip():
                # мод отдал ПУСТОЙ перевод при непустом английском — в игре строка пустая.
                alt = pick_from_chain(src, key, val, skip=cur)
                if ru and ru.strip() and not args_broken(ru, val):
                    merged[key] = ru
                    changed += 1
                elif alt:
                    merged[key] = alt
                    changed += 1
                continue
            if cur is None:
                # перевода нет ни у кого — берём наш
                if ru and ru.strip():
                    merged[key] = ru
                    changed += 1
                continue
            if cur == val:
                # приложили перевод, а там английский текст —
                # перекрываем нашим переводом (иначе в игре остаётся английский)
                alt = pick_from_chain(src, key, val, skip=cur)
                if ru and ru.strip():
                    merged[key] = ru
                    changed += 1
                elif alt:
                    merged[key] = alt
                    changed += 1
                continue
            # у кого-то есть свой перевод — обычно не трогаем его.
            # Исключения: битые %-аргументы, английский текст вместо перевода.
            sig_en = content_signature(val)
            sig_ru = content_signature(cur)
            # %-аргументы сверяем всегда (без них в игре «%s» вместо значения).
            # §-коды, числа и римские цифры — только там, где перевод мода
            # съехал по ключам: в остальных модах перевод вправе менять разметку.
            broken = sig_ru[0] != sig_en[0]
            shifted = ns in STRICT_NS and sig_ru != sig_en
            # Устаревший чужой перевод: мод приложил ru_ru.json от прошлой
            # версии, и числа разошлись с en_us («Deals 25%» → «Возвращает
            # 35%», «Y level -32 and 64» → «на уровне Y 50 и ниже»).
            # Для таких строк есть свежий перевод по английскому тексту —
            # work/stale_fix_ru.json (см. translate_stale_jar.py).
            if not (broken or shifted) and stale_fix:
                fresh = stale_fix.get(val)
                if fresh and fresh.strip() and content_signature(fresh)[0] == sig_en[0]:
                    merged[key] = fresh
                    changed += 1
                    continue
            if broken or shifted:
                alt = pick_from_chain(src, key, val, skip=cur)
                if ru and ru.strip():
                    sig_our = content_signature(ru)
                    match = (sig_our == sig_en) if ns in STRICT_NS else (sig_our[0] == sig_en[0])
                    if match:
                        merged[key] = ru
                        changed += 1
                        continue
                if alt:
                    merged[key] = alt
                    changed += 1
                    continue
                merged[key] = val
                changed += 1
                continue
            if ru and ru.strip() and not CYR.search(cur) and CYR.search(ru):
                # мод приложил «перевод» без единой русской буквы (сдвинутые
                # ключи у terramity, английский текст у mahoutsukai и т.п.) —
                # берём наш перевод, он точно про этот ключ.
                merged[key] = ru
                changed += 1
                continue
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
        # Точечные правки по ключу — ПОСЛЕ основного цикла: они нужны там,
        # где мод сам приложил ru_ru, но часть строк оставил английскими,
        # а ключа нет в en_us.json (словарём по тексту такую не достать).
        for key, ru in key_overrides.get(ns, {}).items():
            if merged.get(key) != ru:
                merged[key] = ru
                changed += 1
        # Дошлифовка (обрывы текста, разнобой «ты/вы») — идёт последней,
        # потому что правит уже готовый текст.
        if polish_fix:
            for key, en_val in en.items():
                fresh = polish_fix.get(en_val) if isinstance(en_val, str) else None
                if fresh and fresh.strip() and merged.get(key) != fresh:
                    merged[key] = fresh
                    changed += 1
        if not changed and not must_write:
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

# Строка-значение, которая на самом деле lang-ключ, а не текст:
# book.mysticalagriculture.crafting, ars_nouveau.page1.sourceberry_bush.
# Patchouli такие строки прогоняет через I18n и берёт перевод из lang-файла,
# поэтому переводить их НЕЛЬЗЯ: перевод («книга.мистическое...крафт») игра
# покажет как есть, а сам ключ перестанет находиться.
LANG_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")


def is_lang_key(text: str) -> bool:
    """Похоже ли значение поля книги на lang-ключ (а не на обычный текст)."""
    s = text.strip()
    if not s or " " in s or "$(" in s or "\n" in s:
        return False
    if s.endswith((".png", ".json", ".nbt", ".snbt")):
        return False
    return bool(LANG_KEY.match(s))


def repair_lang_key(key: str, known: set[str]) -> str:
    """Починит опечатку в ключе книги (mysticalagricultural -> mysticalagriculture).

    Модель иногда «правит» ключ руками, и страница перестаёт находить перевод.
    Возвращаем ближайший существующий ключ, только если совпадение очень
    близкое — иначе ключ не трогаем.
    """
    if key in known:
        return key
    cand = difflib.get_close_matches(key, known, n=1, cutoff=0.94)
    return cand[0] if cand else key


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
    # все ключи, которые вообще существуют в сборке — по ним чиним опечатки
    known_keys: set[str] = set()
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for nm in z.namelist():
            if nm.endswith(("/lang/en_us.json", "/lang/ru_ru.json")):
                try:
                    known_keys.update(load_lang_json(z.read(nm)))
                except Exception:
                    continue
    for jar in sorted(MODS.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        # какие страницы уже имеют ru_ru — только их не трогаем
        has_ru = set()
        for name in z.namelist():
            if "patchouli_books" not in name:
                continue
            parts = name.split("/")
            if "patchouli_books" not in parts:
                continue
            i = parts.index("patchouli_books")
            if len(parts) > i + 2 and parts[i + 2] == "ru_ru":
                has_ru.add((parts[i - 1], parts[i + 1], "/".join(parts[i + 3:])))
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
            rel = Path(*parts[i + 3:]) if len(parts) > i + 3 else Path(name.split("/")[-1])
            if (ns, book, rel.as_posix()) in has_ru:
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
                            # Значение-ключ не переводим: Patchouli сам возьмёт
                            # перевод из lang-файла, а «перевод ключа» ломает
                            # страницу (в игре виден сам ключ).
                            if is_lang_key(v):
                                node[k] = repair_lang_key(v, known_keys)
                                continue
                            ru = translations.get(v)
                            if ru and ru.strip() and not is_lang_key(ru):
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
            target = out / "assets" / ns / "patchouli_books" / book / "ru_ru" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            books += 1
    return books, fields


def adopt_foreign_books(out: Path) -> int:
    """Забирает переведённые книги из чужого пака (MPLOCmods).

    Чужой пак мы убираем из списка — значит его книги должны быть у нас.
    Берём только то, чего у нас нет, и только для модов, что есть в сборке.
    """
    pack = ROOT / "resourcepacks" / "MPLOCmods.zip"
    if not pack.exists():
        return 0
    build_ns = mod_namespaces(MODS)
    prefixes = tuple(f"assets/{ns}/" for ns in sorted(build_ns))
    copied = 0
    for name, data in pack_assets(pack, prefixes).items():
        if "/patchouli_books/" not in name and "/tips/" not in name:
            continue
        target = out / name
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        copied += 1
    return copied


def write_pack_mcmeta(out: Path) -> None:
    (out / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "pack_format": 15,
            "description": "Linggango — русская локализация (переводы модов, книг и интерфейса)",
        }
    }, ensure_ascii=False, indent=1), encoding="utf-8")


# ─────────────────────── шрифт: иконки модов ────────────────────────────────
#
# Проблема: assets/minecraft/font/default.json — ОДИН файл на весь стек паков.
# Кто выше в списке, тот и победил: его файл заменяет модовые целиком.
# В сборке выше mod_resources стоит §6§lVanilla Experience+§0.zip, поэтому
# 61 иконка brutality (и иконки simplyswords/bbb) в игре превращалась в
# квадраты — их провайдеров в итоговом файле просто не было.
#
# Решение: наш пак идёт последним, значит его default.json и есть итоговый.
# Собираем в него провайдеры ВСЕХ модов и всех ВКЛЮЧЁННЫХ ресурспаков.
# Ссылки на include/* оставляем — без них пропадут пробелы и unifont.

DEFAULT_FONT = "assets/minecraft/font/default.json"
FONT_REFS = [
    {"type": "reference", "id": "minecraft:include/space"},
    {"type": "reference", "id": "minecraft:include/default"},
    {"type": "reference", "id": "minecraft:include/unifont"},
]


def _enabled_packs() -> list[str]:
    """Какие ресурспаки включены в options.txt (по именам файлов)."""
    opts = ROOT / "options.txt"
    if not opts.exists():
        return []
    m = re.search(r"resourcePacks:\[(.*?)\]", opts.read_text(encoding="utf-8"), flags=re.S)
    if not m:
        return []
    out = []
    for item in m.group(1).split(","):
        item = item.strip().strip('"')
        if item.startswith("file/"):
            out.append(item[5:])
    return out


def build_default_font(out: Path) -> int:
    """Кладёт в пак объединённый default.json со всеми иконками.

    Возвращает число добавленных bitmap-провайдеров.
    """
    providers: list[dict] = []
    seen_chars: set[str] = set()

    def add_from(path: Path) -> None:
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            return
        if DEFAULT_FONT not in z.namelist():
            return
        try:
            data = json.loads(z.read(DEFAULT_FONT))
        except Exception:
            return
        for prov in data.get("providers", []):
            if prov.get("type") != "bitmap":
                continue
            chars = prov.get("chars")
            chars = "".join(chars) if isinstance(chars, list) else chars
            if not chars or any(c in seen_chars for c in chars):
                continue
            seen_chars.update(chars)
            providers.append(prov)

    # 1) ресурспаки (только включённые — иначе будут битые ссылки на текстуры)
    enabled = _enabled_packs()
    packdir = ROOT / "resourcepacks"
    if packdir.is_dir():
        for f in sorted(packdir.glob("*.zip")):
            if f.name in enabled:
                add_from(f)

    # 2) моды
    for jar in sorted(MODS.glob("*.jar")):
        add_from(jar)

    if not providers:
        return 0

    payload = {"providers": providers + FONT_REFS}
    target = out / DEFAULT_FONT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(providers)


# ─────────────────── подсказки и строки экрана загрузки ─────────────────────
#
# linggango_tweaks берёт их из assets/linggango_tweaks/texts/*.txt через
# ResourceManager (LoadingLines.text/FILE), а не из lang-файлов. Значит наш
# ресурспак может подложить свои — они заменят модовые целиком, как и lang.

TEXTS = [
    ("loading_tips.txt", "loading_tips", "строк"),
    ("loading_lines.txt", "loading_lines", "пар"),
]


def build_texts(out: Path) -> int:
    """Кладёт перевод texts/*.txt. Возвращает число переведённых строк."""
    total = 0
    for fname, stem, unit in TEXTS:
        ru_path = WORK / f"{stem}_ru.json"
        if not ru_path.exists():
            continue
        data = json.loads(ru_path.read_text(encoding="utf-8"))
        if stem == "loading_tips":
            lines = [str(x) for x in data]
        else:
            pairs = [p for p in data if isinstance(p, list) and len(p) == 2]
            en_path = WORK / f"{stem}_en.json"
            if not en_path.exists():
                continue
            en = json.loads(en_path.read_text(encoding="utf-8"))
            table = {k: v for k, v in pairs}
            lines = [table.get(line, line) for line in en]
        target = out / "assets" / "linggango_tweaks" / "texts" / fname
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        total += len([l for l in lines if l.strip()])
        print(f"  texts/{fname}: {len(lines)} {unit}")
    return total


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
    # Свежий перевод строк, где чужой ru_ru.json в jar отстал от en_us.
    stale_fix = {}
    sf_path = WORK / "stale_fix_ru.json"
    if sf_path.exists():
        stale_fix = json.loads(sf_path.read_text(encoding="utf-8"))
        print(f"свежих переводов вместо устаревших: {len(stale_fix)}")
    # Дошлифовка: обрывы текста и разнобой «ты/вы» (fix_polish.py).
    polish_fix = {}
    pf_path = WORK / "polish_fix_ru.json"
    if pf_path.exists():
        polish_fix = json.loads(pf_path.read_text(encoding="utf-8"))
        print(f"дошлифовка: {len(polish_fix)}")
    files, keys = build_lang_files(stage, mod_ru, stale_fix, polish_fix)
    print(f"lang-файлов: {files}, ключей: {keys}")

    po_ru = load_ru("patchouli")
    labels = {}
    lbl_path = WORK / "patchouli_labels_ru.json"
    if lbl_path.exists():
        labels = json.loads(lbl_path.read_text(encoding="utf-8"))
    books, fields = build_patchouli(stage, po_ru, labels)
    print(f"книг: {books}, переведённых полей: {fields}, меток ссылок: {len(labels)}")

    # Переводы книг из чужого пака (MPLOCmods) — забираем к себе, чтобы
    # после удаления чужого пака из списка книги не остались на английском.
    adopted = adopt_foreign_books(stage)
    if adopted:
        print(f"книг из чужого пака: {adopted}")

    write_pack_mcmeta(stage)

    # Иконки шрифтов: наш пак последний, поэтому его default.json — итоговый.
    # Без этого иконки brutality/simplyswords/bbb в игре — квадраты.
    font_providers = build_default_font(stage)
    print(f"иконок в шрифте: {font_providers} провайдеров")

    tip_lines = build_texts(stage)
    print(f"строк экрана загрузки: {tip_lines}")

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

    # Регистрируем пак в конфиге сборки и в options.txt.
    # ВАЖНО: список паков упорядочен от низшего приоритета к высшему,
    # поэтому наш пак должен быть ПОСЛЕДНИМ — иначе его перекроют
    # чужие локализации (MPLOCmods и т.п.).
    entry = f'"file/{PACK_NAME}.zip"'
    foreign = '"file/MPLOCmods.zip"'

    def put_last(text: str, prefix: str) -> str:
        """Ставит запись последней в списке паков (и убирает старую копию)."""
        m = re.search(re.escape(prefix) + r"\[(.*?)\]", text, flags=re.S)
        if not m:
            return text
        items = [it.strip() for it in m.group(1).split(",") if it.strip()]
        items = [it for it in items if it != entry]
        items.append(entry)
        return text[:m.start(1)] + ", ".join(items) + text[m.end(1):]

    def drop_foreign(text: str, prefix: str) -> str:
        """Убирает чужой локализационный пак: он нам больше не нужен."""
        m = re.search(re.escape(prefix) + r"\[(.*?)\]", text, flags=re.S)
        if not m:
            return text
        items = [it.strip() for it in m.group(1).split(",") if it.strip()]
        if foreign not in items:
            return text
        items = [it for it in items if it != foreign]
        return text[:m.start(1)] + ", ".join(items) + text[m.end(1):]

    toml = ROOT / "config/linggango-resourcepacks.toml"
    text = toml.read_text(encoding="utf-8")
    new_text = put_last(text, "packs = ")
    new_text = drop_foreign(new_text, "packs = ")
    if new_text != text:
        toml.write_text(new_text, encoding="utf-8")
        print("наш пак последний в linggango-resourcepacks.toml, MPLOCmods убран")

    opts = ROOT / "options.txt"
    otext = opts.read_text(encoding="utf-8")
    new_otext = put_last(otext, "resourcePacks:")
    new_otext = drop_foreign(new_otext, "resourcePacks:")
    if new_otext != otext:
        opts.write_text(new_otext, encoding="utf-8")
        print("наш пак последний в options.txt, MPLOCmods убран")


if __name__ == "__main__":
    main()
