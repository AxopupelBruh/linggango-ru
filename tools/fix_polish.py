#!/usr/bin/env python3
"""Дошлифовка перевода: обрывы текста и разнобой «ты/вы» внутри одной строки.

Две проблемы, обе не ломают игру, но видны игроку:

1) ОБРЫВ. Перевод в 2+ раза короче оригинала — часть смысла потеряна
   («Place it down and wait, to hatch Skeloraptor...» → «Перезарядка Рева:»).
   Такие строки переводим заново с английского.

2) РАЗНОБОЙ. В одной строке и «ты», и «вы»
   («У тебя нога отказала. Вам придётся ползти»). Просим модель переписать
   строку единообразно, на «вы» — это основной стиль пака (5448 против 754).

Результат — work/polish_fix_ru.json: {английский текст: исправленный русский}.
Сборщик применяет его последним, поверх чужих переводов.

Запуск:
    python3 fix_polish.py --dry-run
    python3 fix_polish.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import INSTANCE  # noqa: E402

HERE = Path(__file__).resolve().parent
MODS = INSTANCE / "mods"
WORK = HERE / "work"
OUT = WORK / "polish_fix_ru.json"

TY = re.compile(
    r"\b(ты|тебя|тебе|тобой|твой|твоя|твоё|твое|твои|твоего|твою|твоим|твоих"
    r"|сделай|нажми|возьми|поставь|используй|держи|щёлкни|щелкни|убей|найди"
    r"|открой|положи|проверь|посмотри|знаешь|хочешь|можешь)\b", re.I)
VY = re.compile(
    r"\b(вы|вас|вам|вами|ваш|ваша|ваше|ваши|вашего|вашу|вашим|ваших"
    r"|сделайте|нажмите|возьмите|поставьте|используйте|держите|щёлкните"
    r"|щелкните|убейте|найдите|откройте|положите|проверьте|посмотрите)\b", re.I)

RE_CODE = re.compile(r"§.")
RE_ARG = re.compile(r"%(?:\d+\$)?[sdif]")


def clean(text: str) -> str:
    out = RE_CODE.sub("", text)
    out = re.sub(r"\$\([^)]*\)", "", out)
    out = re.sub(r"<[^>]+>", "", out)
    out = re.sub(r"@L@|%%n|\{\{?[^}]*\}?\}", "", out)
    return out


def load_lang(data: bytes) -> dict:
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            obj = json.loads(data.decode(enc))
        except Exception:
            continue
        return obj if isinstance(obj, dict) else {}
    return {}


def collect() -> tuple[dict, dict]:
    """en_us из jar-ов + текущий ru_ru из собранного ресурспака.

    Важно: русский берём ИЗ ПАКА, а не из jar. В jar лежит чужой перевод,
    который сборщик может перекрыть нашим — иначе правили бы не то, что
    реально видит игрок.
    """
    en_by_ns: dict[str, dict] = {}
    ru_by_ns: dict[str, dict] = {}
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
            ns = folder.split("/")[1]
            target = en_by_ns if fname == "en_us.json" else ru_by_ns
            target.setdefault(ns, {}).update(load_lang(z.read(name)))

    pack = INSTANCE / "resourcepacks" / "zz_linggango_ru.zip"
    if pack.exists():
        ru_by_ns = {}
        with zipfile.ZipFile(pack) as z:
            for name in z.namelist():
                if not name.startswith("assets/") or not name.endswith("/lang/ru_ru.json"):
                    continue
                ns = name.split("/")[1]
                ru_by_ns.setdefault(ns, {}).update(load_lang(z.read(name)))
    return en_by_ns, ru_by_ns


def find_truncated(en_by_ns: dict, ru_by_ns: dict) -> list[str]:
    """Английские тексты, чей перевод сильно короче оригинала."""
    out = []
    for ns, en in en_by_ns.items():
        ru = ru_by_ns.get(ns, {})
        for key, val in en.items():
            if not isinstance(val, str) or len(clean(val).strip()) < 40:
                continue
            cur = ru.get(key)
            if not isinstance(cur, str) or not re.search(r"[а-яёА-ЯЁ]", cur):
                continue
            if len(clean(cur).strip()) / max(len(clean(val).strip()), 1) < 0.45:
                out.append(val)
    return out


def find_mixed(en_by_ns: dict, ru_by_ns: dict) -> list[tuple[str, str]]:
    """Пары (английский, русский), где в переводе смешаны «ты» и «вы»."""
    out = []
    for ns, en in en_by_ns.items():
        ru = ru_by_ns.get(ns, {})
        for key, cur in ru.items():
            if not isinstance(cur, str):
                continue
            if not (TY.search(cur) and VY.search(cur)):
                continue
            src = en.get(key)
            if isinstance(src, str) and src.strip():
                out.append((src, cur))
    return out


def translate(lines: list[str]) -> dict[str, str]:
    import concurrent.futures as cf
    from deepseek_backend import DeepSeekBackend

    def make_backend() -> DeepSeekBackend:
        b = DeepSeekBackend()
        orig = b.session.post

        def post(url, **kw):
            kw.setdefault("timeout", 120)
            return orig(url, **kw)

        b.session.post = post
        return b

    done: dict[str, str] = {}
    step = 10
    chunks = [lines[i:i + step] for i in range(0, len(lines), step)]

    def do_chunk(part: list[str]) -> dict[str, str]:
        b = make_backend()
        for _ in range(2):
            try:
                return dict(zip(part, b.translate_batch(part)))
            except Exception as exc:  # noqa: BLE001
                print(f"  ошибка пачки ({len(part)}): {exc}", flush=True)
                time.sleep(3)
        return {}

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(do_chunk, chunks):
            for src, tr in res.items():
                if tr and tr.strip() and tr != src:
                    done[src] = tr
    return done


def rewrite_mixed(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """Просим модель переписать строку единообразно, на «вы»."""
    import concurrent.futures as cf
    from deepseek_backend import DeepSeekBackend

    out: dict[str, str] = {}
    step = 10
    chunks = [pairs[i:i + step] for i in range(0, len(pairs), step)]

    def do_chunk(part: list[tuple[str, str]]) -> dict[str, str]:
        b = DeepSeekBackend()
        orig = b.session.post

        def post(url, **kw):
            kw.setdefault("timeout", 120)
            return orig(url, **kw)

        b.session.post = post

        payload = json.dumps(
            [{"en": src, "ru": ru} for src, ru in part], ensure_ascii=False)
        prompt = (
            "Ниже строки локализации Minecraft. Поле ru — готовый русский "
            "перевод, в котором смешаны обращения «ты» и «вы». Перепиши ru "
            "единообразно, обращаясь к игроку на «вы» (глаголы и местоимения "
            "согласуй). Смысл, форматирование (§-коды, <теги>, %s, @L@, "
            "переносы строк) сохрани без изменений. Строки должны остаться "
            "такой же длины по смыслу — ничего не выбрасывай.\n"
            f"{payload}\n"
            "Верни JSON-массив объектов {\"ru\": \"...\"} в том же порядке, "
            "без пояснений."
        )
        res: dict[str, str] = {}
        for _ in range(2):
            try:
                body = b._request_raw(prompt)  # noqa: SLF001
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  ошибка пачки ты/вы ({len(part)}): {exc}", flush=True)
                time.sleep(3)
        else:
            return res
        try:
            got = json.loads(body)
        except Exception:
            m = re.search(r"\[.*\]", body, re.S)
            if not m:
                return res
            try:
                got = json.loads(m.group(0))
            except Exception:
                return res
        if not isinstance(got, list) or len(got) != len(part):
            return res
        for (src, old), item in zip(part, got):
            new = item.get("ru") if isinstance(item, dict) else None
            if not isinstance(new, str) or not new.strip():
                continue
            if sorted(RE_ARG.findall(new)) != sorted(RE_ARG.findall(old)):
                continue
            if sorted(RE_CODE.findall(new)) != sorted(RE_CODE.findall(old)):
                continue
            res[src] = new
        return res

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(do_chunk, chunks):
            out.update(res)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=("trunc", "mixed"), default=None)
    args = ap.parse_args()

    en_by_ns, ru_by_ns = collect()
    trunc = find_truncated(en_by_ns, ru_by_ns)
    mixed = find_mixed(en_by_ns, ru_by_ns)

    known = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    trunc = [t for t in trunc if t not in known]
    mixed = [(s, r) for s, r in mixed if s not in known]

    print(f"обрывов: {len(trunc)} | строк со смешанным ты/вы: {len(mixed)}")
    if args.dry_run:
        for t in trunc[:12]:
            print(f"   обрыв: {t[:110]!r}")
        for s, r in mixed[:8]:
            print(f"   ты/вы: {r[:110]!r}")
        return

    if args.only != "mixed" and trunc:
        known.update(translate(trunc))
        print(f"после обрывов: {len(known)}")
    if args.only != "trunc" and mixed:
        known.update(rewrite_mixed(mixed))
        print(f"после ты/вы: {len(known)}")

    OUT.write_text(json.dumps(known, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")
    print(f"записано в {OUT}: {len(known)}")


if __name__ == "__main__":
    main()
