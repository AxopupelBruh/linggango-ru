"""Перевод строк, зашитых в Java-код модов, и патч jar-файлов.

Что делает:
  1. Берёт строки из work/java_strings.json (собраны scan_java_strings.py).
  2. Режет их по §-кодам, маскирует термины из work/terms_mined.json
     плейсхолдерами {0}, {1}... и переводит через DeepL API Free.
  3. Возвращает §-коды на места, подставляет термины (в нужном регистре).
  4. Патчит .class-файлы (пересборка constant pool) и пересобирает jar.

Запуск:
    python3 fix_java_strings.py                  # только перевести, показать
    python3 fix_java_strings.py --apply         # перевести и пропатчить jar
    python3 fix_java_strings.py --apply --jars terramity-0.9.8-forge-1.20.1.jar
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = INSTANCE
MODS = ROOT / "mods"
WORK = HERE / "work"
BACKUP = HERE / "backup" / "jars_original"
CACHE = WORK / "cache_deepl.json"
OUT_MAP = WORK / "java_strings_ru.json"

sys.path.insert(0, str(HERE))
from classfile import ClassFile, patch_class  # noqa: E402
from deepl_backend import DeepLBackend, split_by_codes, split_ws  # noqa: E402

CODE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
CYR = re.compile(r"[а-яёА-ЯЁ]")


def load_terms() -> dict[str, str]:
    p = WORK / "terms_mined.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    # только «чистые» формы: без висячей пунктуации
    return {k: v for k, v in raw.items() if v.strip() and not re.search(r"[.,;:]$", v.strip())}


WORD = re.compile(r"[A-Za-z][A-Za-z0-9'’\-]*")
# после этих слов термин не маскируем — пусть DeepL сам склоняет
PREPOSITIONS = {"with", "of", "by", "for", "from", "to", "on", "in", "into",
                "and", "or", "the", "a", "an", "at", "as", "than", "that"}


def _term_index(terms: dict[str, str]) -> dict[str, list[str]]:
    """Индекс глоссария по первому слову — для быстрого подбора фраз."""
    idx: dict[str, list[str]] = {}
    for key in terms:
        idx.setdefault(key.split()[0], []).append(key)
    for v in idx.values():
        v.sort(key=len, reverse=True)
    return idx


def mask_terms(text: str, terms: dict[str, str],
               index: dict[str, list[str]] | None = None) -> tuple[str, list[str]]:
    """Заменяет термины глоссария на {N}-плейсхолдеры (DeepL их не трогает).

    Сопоставление строго по регистру: иначе обычное слово («by») находило бы
    термин с другой формой («By») и подставлялось не то.
    Фразы из 2-3 слов ищутся целиком — иначе «Life Steal» не попал бы в
    маску внутри «Grants Life Steal».
    """
    if not terms:
        return text, []
    idx = index if index is not None else _term_index(terms)
    found: list[str] = []
    out: list[str] = []
    pos = 0
    n = len(text)
    prev_word = ""
    while pos < n:
        m = WORD.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        # собираем до трёх слов подряд
        words = []
        for w in WORD.finditer(text, m.start()):
            words.append(w)
            if len(words) == 3:
                break
        repl = None
        used = m.end()
        # после предлога термин не маскируем: склонение должен сделать DeepL
        blocked = prev_word.lower() in PREPOSITIONS
        if not blocked:
            for cnt in range(min(3, len(words)), 0, -1):
                phrase = " ".join(w.group(0) for w in words[:cnt])
                if phrase in terms:
                    repl = phrase
                    used = words[cnt - 1].end()
                    break
        if repl:
            found.append(repl)
            out.append("{%d}" % (len(found) - 1))
        else:
            out.append(m.group(0))
        prev_word = m.group(0)
        pos = used
    return "".join(out), found


def unmask_terms(text: str, found: list[str], terms: dict[str, str]) -> str:
    """Подставляет перевод термина. Регистр — как в оригинале:
    «Grants» → «Даёт» (с большой), «grants» → «даёт»."""
    def repl(m: re.Match) -> str:
        i = int(m.group(1))
        if i >= len(found):
            return m.group(0)
        term = found[i]
        ru = terms.get(term, "")
        if term[:1].islower() and ru[:1].isupper():
            ru = ru[0].lower() + ru[1:]
        return ru

    return re.sub(r"\{(\d+)\}", repl, text)


def translate_all(strings: list[str], backend: DeepLBackend,
                  terms: dict[str, str]) -> dict[str, str]:
    tindex = _term_index(terms)
    """Переводит строки, сохраняя §-коды и термины."""
    # готовим задания: (core, found_terms, mid_sentence)
    jobs: list[tuple[str, list[str], bool]] = []
    layout: list[list[tuple[int, str, str, list[str]]]] = []
    for text in strings:
        row = []
        for chunk, _codes in split_by_codes(text):
            lead, core, trail = split_ws(chunk)
            masked, found = mask_terms(core, terms, tindex)
            mid = bool(lead) or not text.startswith(chunk)
            row.append((len(jobs), lead, trail, found))
            jobs.append((masked, found, mid))
        layout.append(row)

    cores = [j[0] for j in jobs if j[0].strip()]
    uniq = list(dict.fromkeys(cores))
    translated: dict[str, str] = {}
    for i in range(0, len(uniq), backend.max_items):
        batch = uniq[i:i + backend.max_items]
        for src, ru in zip(batch, backend.translate(batch)):
            translated[src] = ru

    result: dict[str, str] = {}
    for text, row in zip(strings, layout):
        parts = split_by_codes(text)
        buf = ""
        for (idx, lead, trail, found), (chunk, codes) in zip(row, parts):
            _l, core, _t = split_ws(chunk)
            masked, found2 = mask_terms(core, terms, tindex)
            ru = translated.get(masked, core) if core.strip() else core
            ru = unmask_terms(ru, found2, terms)
            buf += "".join(codes) + lead + ru + trail
        result[text] = buf
    return result


def validate(en: str, ru: str) -> str | None:
    if CODE.findall(en) != CODE.findall(ru):
        return "разошлись §-коды"
    if re.search(r"\{\d+\}", ru):
        return "остались плейсхолдеры"
    if not ru.strip():
        return "пусто"
    return None


def postprocess(en: str, ru: str) -> str:
    """Чистит артефакты DeepL: пробел перед «%», лишние кавычки."""
    out = ru
    # DeepL ставит пробел перед знаком процента: «98 %» → «98%»
    out = re.sub(r"(?<=\d) ?%", "%", out)
    # кавычки, которых не было в оригинале
    if not re.search(r"[«»\"']", en):
        out = out.replace("«", "").replace("»", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="патчить jar-файлы")
    ap.add_argument("--jars", nargs="*", default=None, help="ограничить список jar-файлов")
    ap.add_argument("--batch", type=int, default=30)
    args = ap.parse_args()

    src = json.loads((WORK / "java_strings.json").read_text(encoding="utf-8"))
    terms = load_terms()
    strings = list(src)
    cache: dict[str, str] = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    # приоритет: уже готовый перевод из карты пакета (сделан DeepSeek, согласован
    # с остальным модпаком) — DeepL используем только для остального
    mods_map = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    from_map: dict[str, str] = {}
    for s in strings:
        v = mods_map.get(s)
        if isinstance(v, str) and v != s and CYR.search(v) and not re.search(r"\{\d+\}", v):
            from_map[s] = v
    pending = [s for s in strings if s not in from_map and s not in cache]
    print(f"строк в коде модов: {len(strings)}, терминов в глоссарии: {len(terms)}")
    print(f"взято из карты пакета: {len(from_map)}, в кэше: "
          f"{len([s for s in strings if s in cache and s not in from_map])}, к переводу: {len(pending)}")

    backend = DeepLBackend()
    if pending:
        out = translate_all(pending, backend, terms)
        cache.update(out)
    # пост-обработка применяется ко всему кэшу (и к ранее переведённому)
    cache = {k: postprocess(k, v) for k, v in cache.items()}
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    cache.update(from_map)
    bad = [(s, cache.get(s, "")) for s in strings if validate(s, cache.get(s, ""))]
    good = {s: cache[s] for s in strings if s in cache and not validate(s, cache[s])}
    OUT_MAP.write_text(json.dumps(good, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"переведено и проверено: {len(good)}, отклонено: {len(bad)}")
    for en, ru in bad[:10]:
        print(f"   [{validate(en, ru)}] {en[:60]!r} -> {ru[:60]!r}")

    print("\nпримеры:")
    for en in list(good)[:12]:
        print(f"   {en[:64]!r}\n     -> {good[en][:64]!r}")

    if not args.apply:
        print("\n(без --apply jar-файлы не трогаются)")
        return 0

    # ---- патчим jar-файлы -------------------------------------------------
    jars = sorted({loc.split("|")[0] for locs in src.values() for loc in locs})
    if args.jars:
        jars = [j for j in jars if j in args.jars]
    BACKUP.mkdir(parents=True, exist_ok=True)

    for jar_name in jars:
        jar_path = MODS / jar_name
        if not jar_path.exists():
            print(f"нет jar: {jar_name}")
            continue
        bak = BACKUP / jar_name
        if not bak.exists():
            shutil.copy2(jar_path, bak)
        # какие строки патчить в этом jar
        repl_by_class: dict[str, dict[str, str]] = {}
        for en, locs in src.items():
            ru = good.get(en)
            if not ru or ru == en:
                continue
            for loc in locs:
                if loc.split("|")[0] != jar_name:
                    continue
                cls = loc.split("|")[1]
                repl_by_class.setdefault(cls, {})[en] = ru

        tmp = jar_path.with_suffix(".jar.tmp")
        patched_classes = 0
        with zipfile.ZipFile(jar_path) as zin, \
                zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename in repl_by_class:
                    out, n = patch_class(data, repl_by_class[item.filename])
                    if n:
                        data = out
                        patched_classes += 1
                zout.writestr(item, data)
        if patched_classes:
            tmp.replace(jar_path)
            print(f"пропатчено классов: {patched_classes}  ({jar_name})")
        else:
            tmp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
