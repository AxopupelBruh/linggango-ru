"""Все источники переводов ru_ru, которые видны в игре.

Ресурспак с lang-файлом **ЗАМЕНЯЕТ** файл мода целиком, а не дополняет его.
Значит наш пак обязан держать объединение всех источников сразу, иначе
достаточно убрать чужой пак из списка — и часть переводов исчезнет.

Источники (от низшего приоритета к высшему, как их видит игра):

1. ``assets/<ns>/lang/ru_ru.json`` внутри jar-ов модов;
2. пак KubeJS — ``kubejs/assets/<ns>/lang/ru_ru.json``;
3. пак serilum — ``data/serilum/translations/assets/<ns>/lang/ru_ru.json``;
4. чужие локализации — ``MPLOCmods.zip`` (если он есть в сборке).

Поверх всего — наши собственные переводы.
"""
from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from pathlib import Path


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_zip_json(z: zipfile.ZipFile, name: str):
    try:
        return json.loads(z.read(name).decode("utf-8"))
    except Exception:
        return None


def _clean(data) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def mod_namespaces(mods_dir: Path) -> set[str]:
    """Неймспейсы, которые реально есть в сборке (каталоги assets/<ns>/ в jar-ах)."""
    out: set[str] = set()
    for jar in sorted(mods_dir.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if name.startswith("assets/") and name.count("/") >= 2:
                out.add(name.split("/")[1])
    return out


def mod_lang(mods_dir: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """(en_us, ru_ru) из jar-ов модов — по неймспейсам."""
    en: dict[str, dict[str, str]] = defaultdict(dict)
    ru: dict[str, dict[str, str]] = defaultdict(dict)
    for jar in sorted(mods_dir.glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in z.namelist():
            if not name.startswith("assets/") or "/lang/" not in name:
                continue
            folder, fname = name.rsplit("/", 1)
            if fname not in ("en_us.json", "ru_ru.json"):
                continue
            data = _clean(_read_zip_json(z, name))
            if not data:
                continue
            ns = folder.split("/")[1]
            (en if fname == "en_us.json" else ru)[ns].update(data)
    return en, ru


def dir_lang(root: Path) -> dict[str, dict[str, str]]:
    """ru_ru из каталога вида <root>/assets/<ns>/lang/ru_ru.json."""
    out: dict[str, dict[str, str]] = {}
    base = root / "assets"
    if not base.is_dir():
        return out
    for lang in sorted(base.glob("*/lang/ru_ru.json")):
        ns = lang.relative_to(base).parts[0]
        data = _clean(_read_json(lang))
        if data:
            out.setdefault(ns, {}).update(data)
    return out


def pack_lang(pack: Path, only: set[str] | None = None) -> dict[str, dict[str, str]]:
    """ru_ru из ресурспака. only — оставить только эти неймспейсы."""
    out: dict[str, dict[str, str]] = {}
    if not pack.exists():
        return out
    try:
        z = zipfile.ZipFile(pack)
    except Exception:
        return out
    for name in z.namelist():
        if not (name.startswith("assets/") and name.endswith("/lang/ru_ru.json")):
            continue
        ns = name.split("/")[1]
        if only is not None and ns not in only:
            continue
        data = _clean(_read_zip_json(z, name))
        if data:
            out.setdefault(ns, {}).update(data)
    return out


def pack_assets(pack: Path, prefixes: tuple[str, ...]) -> dict[str, bytes]:
    """Файлы ресурспака по префиксам (например assets/<ns>/patchouli_books/)."""
    out: dict[str, bytes] = {}
    if not pack.exists():
        return out
    try:
        z = zipfile.ZipFile(pack)
    except Exception:
        return out
    for name in z.namelist():
        if name.endswith("/"):
            continue
        if any(name.startswith(p) for p in prefixes):
            try:
                out[name] = z.read(name)
            except Exception:
                continue
    return out


def save_mploc_snapshot(target: Path, data: dict[str, dict[str, str]]) -> None:
    """Сохраняет перенятые чужие переводы — чтобы сборка не зависела от наличия пака."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_mploc_snapshot(target: Path) -> dict[str, dict[str, str]]:
    data = _read_json(target)
    if not isinstance(data, dict):
        return {}
    return {ns: _clean(d) for ns, d in data.items() if isinstance(d, dict)}
