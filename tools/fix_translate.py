"""Починка непереведённых строк перевода Linggango через LLM (DeepSeek / Gemini).

Что делает:
  1. Берёт список непереведённых EN-строк (work/fix_targets.json).
  2. Защищает только разметку Minecraft (§-коды, теги, плейсхолдеры, ID) —
     tr_engine.Protector в режиме mode="none", keep_spaces=True.
     Термины глоссария НЕ маскируются: жёсткая подстановка ломала смысл
     («Target»→«Мишень» вместо «цель») и не склонялась по-русски.
  3. Собирает подсказки по терминам (многословные термины глоссария и уже
     готовые переводы work/mods_ru.json) и передаёт их модели — так терминология
     остаётся единой, но остаётся живой русский текст.
  4. Переводит батчами (DeepSeek V4.1 Flash по умолчанию) с ретраями.
  5. Проверяет результат: плейсхолдеры, коды цвета, токены, кириллица; откатывает
     транслитерации брендов (brands.restore_brands).
  6. Складывает переводы в work/mods_ru.json и в кэш work/cache_<backend>.json.

Запуск:
    python3 fix_translate.py                       # доделать незавершённое
    python3 fix_translate.py --limit 40 --dry-run  # показать выборку
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"

sys.path.insert(0, str(HERE))
from brands import restore_brands  # noqa: E402
from tr_engine import (RE_COLOR, RE_FILE, RE_HEX, RE_ID, RE_PLACEHOLDER,  # noqa: E402
                       RE_TAG, RE_URL, Protector)

PLACE = re.compile(r"%[-+0-9.#]*[a-zA-Z]|\{\d+\}|\{\}")
TOKEN_RE = re.compile(r"\[\[(\d+)\]\]")
CYR = re.compile(r"[а-яёА-ЯЁ]")


def meaningful(s: str) -> bool:
    x = PLACE.sub("", s)
    x = RE_COLOR.sub("", x)
    x = re.sub(r"[\s\[\](){}<>|.,:;!?/\\*#@&+=\-–—~^%$'\"]", "", x)
    return bool(x.strip())


def sig(s: str) -> tuple:
    """Сигнатура, которую перевод обязан сохранить."""
    return (
        tuple(sorted(PLACE.findall(s))),
        tuple(sorted(RE_COLOR.findall(s))),
        tuple(sorted(RE_HEX.findall(s))),
        tuple(sorted(RE_TAG.findall(s))),
        tuple(sorted(RE_URL.findall(s))),
        tuple(sorted(RE_ID.findall(s))),
    )


def keep_edges(en: str, ru: str) -> str:
    """Возвращает ведущие/завершающие пробелы оригинала к переводу."""
    lead = en[:len(en) - len(en.lstrip())]
    trail = en[len(en.rstrip()):]
    return lead + ru.strip() + trail


def check(ru: str, en: str) -> str | None:
    """Возвращает причину отбраковки или None, если перевод хорош."""
    if not ru or not ru.strip():
        return "пустой перевод"
    if sig(ru) != sig(en):
        return "разошлись плейсхолдеры/коды"
    if TOKEN_RE.search(ru):
        return "остались токены"
    if ru == en and meaningful(en):
        return "перевод совпал с оригиналом"
    if meaningful(en) and not CYR.search(ru):
        return "в переводе нет кириллицы"
    return None


# строка, где каждое слово с заглавной буквы — похожа на имя собственное
PROPER = re.compile(r"^[\W\d_]*(\W|\d|[\w'’-]+)(\s|$)")


def looks_like_name(en: str) -> bool:
    """Похоже ли английское имя на имя собственное (перевод не нужен)."""
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", en)
    if not words:
        return False
    return all(w[:1].isupper() or w.lower() in ("of", "the", "and", "or", "de", "la") for w in words)


def check_relaxed(ru: str, en: str) -> str | None:
    """Мягкая проверка: имя собственное оставляем как есть."""
    reason = check(ru, en)
    if reason in ("перевод совпал с оригиналом", "в переводе нет кириллицы") and looks_like_name(en):
        return None
    return reason


class Hints:
    """Подсказки по терминам: многословные термины глоссария + готовые переводы."""

    def __init__(self, glossary: dict, mods_ru: dict, max_hints: int = 8):
        self.max_hints = max_hints
        self.glossary: dict[str, str] = {}
        for en, val in glossary.items():
            if not isinstance(val, dict) or not val.get("ru"):
                continue
            if " " not in en.strip():
                continue  # однословные термины слишком рискованные («Target»→«Мишень»)
            if val["ru"].strip().lower() == en.strip().lower():
                continue  # «перевод» совпадает с оригиналом — подсказка бессмысленна
            self.glossary[en.strip()] = val["ru"]
        self.term_re = None
        if self.glossary:
            alts = "|".join(re.escape(t) for t in sorted(self.glossary, key=len, reverse=True))
            self.term_re = re.compile(rf"(?<![\w])({alts})(?![\w])", re.IGNORECASE)
        # уже готовые переводы пакета: многословные ключи
        self.ready = [(k, v) for k, v in mods_ru.items()
                      if " " in k and 8 <= len(k) <= 40 and v.strip()
                      and v.strip().lower() != k.strip().lower()]

    def for_string(self, en: str) -> dict[str, str]:
        hints: dict[str, str] = {}
        if self.term_re:
            for m in self.term_re.finditer(en):
                term = m.group(1)
                ru = self.glossary.get(term) or self.glossary.get(term.lower())
                if ru and term not in hints:
                    hints[term] = ru
                if len(hints) >= self.max_hints:
                    break
        low = en.lower()
        for k, v in self.ready:
            if k.lower() in low:
                hints.setdefault(k, v)
                if len(hints) >= self.max_hints:
                    break
        return hints


def build_backend(name: str, model: str | None):
    if name == "deepseek":
        from deepseek_backend import DeepSeekBackend
        return DeepSeekBackend(model=model or "deepseek-v4.1-flash-free")
    if name == "gemini":
        from gemini_backend import GeminiBackend
        return GeminiBackend(model=model or "gemini-3.1-flash-lite")
    raise SystemExit(f"неизвестный бэкенд: {name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--jobs", type=int, default=4, help="сколько запросов параллельно")
    ap.add_argument("--limit", type=int, default=0, help="ограничить число строк (для теста)")
    ap.add_argument("--backend", default="deepseek", choices=("deepseek", "gemini"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--retry-from", default=None,
                    help="файл с отбракованными переводами (json: [{en,ru,why}]) — "
                         "повторный проход по ним")
    ap.add_argument("--relaxed", action="store_true",
                    help="мягкая приёмка: имена собственные оставляем как есть")
    args = ap.parse_args()

    targets = json.loads((WORK / "fix_targets.json").read_text(encoding="utf-8"))
    todo = [s for s in targets["todo"] if meaningful(s)]
    if args.limit:
        todo = todo[:args.limit]
    print(f"строк к переводу: {len(todo)}")

    cache_path = WORK / f"cache_{args.backend}.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    mods_ru: dict[str, str] = json.loads((WORK / "mods_ru.json").read_text(encoding="utf-8"))
    glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))
    # mode="none" — термины глоссария не маскируем; keep_spaces=True — LLM теряет текст,
    # если пробелы заменены токенами
    prot = Protector(glossary, mode="none", keep_spaces=True)
    hints = Hints(glossary, mods_ru)

    pending = [s for s in todo if not cache.get(s)]
    if args.retry_from:
        data = json.loads(Path(args.retry_from).read_text(encoding="utf-8"))
        pending = [it["en"] for it in data if isinstance(it, dict) and it.get("en")]
        print(f"повторный проход по {len(pending)} отбракованным строкам")
    print(f"из них уже переведено ранее (кэш): {len(todo) - len(pending)}, в очереди: {len(pending)}")
    if args.dry_run:
        for s in pending[:20]:
            print("   ", repr(s[:80]), "→", hints.for_string(s))
        return 0
    if not pending:
        print("нечего переводить")
        return 0

    backend = build_backend(args.backend, args.model)
    masked: dict[str, tuple[str, list[str]]] = {s: prot.protect(s) for s in pending}
    chunks = [pending[i:i + args.batch] for i in range(0, len(pending), args.batch)]

    ok: dict[str, str] = {}
    bad: list[tuple[str, str, str]] = []
    done = [0]

    def save_cache() -> None:
        cache.update(ok)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    def do_chunk(chunk: list[str]) -> list[tuple[str, str, str | None]]:
        payload = [{"en": masked[s][0], "terms": hints.for_string(s)} for s in chunk]
        try:
            out = backend.translate_batch_hinted(payload)
        except Exception as exc:  # noqa: BLE001
            return [(s, "", f"ошибка запроса: {exc}") for s in chunk]
        res = []
        for s, ru in zip(chunk, out):
            full = keep_edges(s, prot.restore(ru, masked[s][1]))
            full = restore_brands(s, full)
            reason = check_relaxed(full, s) if args.relaxed else check(full, s)
            res.append((s, full, reason))
        return res

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for res in pool.map(do_chunk, chunks):
            for s, ru, reason in res:
                if reason:
                    bad.append((s, ru, reason))
                else:
                    ok[s] = ru
            done[0] += 1
            save_cache()  # кэш пишем на лету, чтобы не потерять работу при сбое
            if done[0] % 5 == 0 or done[0] == len(chunks):
                el = time.time() - t0
                print(f"[{done[0]}/{len(chunks)}] готово: {len(ok)}, отбраковано: {len(bad)}, "
                      f"{el:.0f}s, запросов: {backend.calls}", flush=True)

    cache.update(ok)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    added = 0
    for s, ru in ok.items():
        if s not in mods_ru:
            mods_ru[s] = ru
            added += 1
        elif mods_ru[s] != ru:
            mods_ru[s] = ru
    (WORK / "mods_ru.json").write_text(json.dumps(mods_ru, ensure_ascii=False, indent=1),
                                        encoding="utf-8")

    (WORK / f"fix_rejected_{args.backend}.json").write_text(
        json.dumps([{"en": a, "ru": b, "why": c} for a, b, c in bad], ensure_ascii=False, indent=1),
        encoding="utf-8")

    print(f"\nпереведено и записано в mods_ru.json: {len(ok)} (новых: {added})")
    print(f"отбраковано: {len(bad)} → work/fix_rejected_{args.backend}.json")
    for a, b, c in bad[:10]:
        print(f"   [{c}] {a[:60]!r} → {b[:60]!r}")
    print(f"запросов к бэкенду: {backend.calls}, "
          f"вход {backend.input_chars/1000:.0f}k симв., выход {backend.output_chars/1000:.0f}k симв.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
