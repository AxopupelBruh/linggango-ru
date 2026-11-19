"""Автопилот догона DeepSeek-переводов подсказок.

Провайдер 100milionseek нестабилен (503/524) и держит ~4 одновременные сессии,
поэтому переводим раундами: N пулов на N ключей, каждый получает свой кусок
НЕПЕРЕВЕДЁННЫХ строк (общий кэш-сид => разбиение без дублей).

Когда покрытие полное — сливает кэши, пересобирает словарь, скрипт и тесты.

Запуск: python3 deepseek_driver.py [--pools 4] [--rounds 50]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"


def pool_caches() -> list[Path]:
    return [WORK / f"cache_deepseek_ui_p{i}.json" for i in range(7)]


def union_map() -> dict[str, str]:
    """Ключ → перевод (из всех пулов; берём первый непустой)."""
    out: dict[str, str] = {}
    for p in pool_caches():
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if v and k not in out:
                out[k] = v
    return out


def seed_all(union: dict[str, str]) -> None:
    """Каждому пулу кладём общий словарь: pending считается одинаково,
    разбиение --parts/--part даёт непересекающиеся куски."""
    for p in pool_caches():
        cur = {}
        if p.exists():
            try:
                cur = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                cur = {}
        merged = {k: v for k, v in cur.items() if v}
        for k, v in union.items():
            merged.setdefault(k, v)
        p.write_text(json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")


def real_count() -> int:
    """Сколько ключей реально переведено (непустое значение)."""
    n = 0
    seen: set[str] = set()
    for p in pool_caches():
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if v and k not in seen:
                seen.add(k)
                n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=50)
    ap.add_argument("--total", type=int, default=7998)
    args = ap.parse_args()

    for rnd in range(1, args.rounds + 1):
        done = real_count()
        print(f"[{time.strftime('%H:%M:%S')}] раунд {rnd}: переведено {done}/{args.total}",
              flush=True)
        if done >= args.total:
            break

        # сидим все пулы общим объединением — разбиение будет по общему остатку
        union = union_map()
        seed_all(union)

        procs = []
        for i in range(args.pools):
            key = HERE / (".deepseek_key" if i == 0 else f".deepseek_key{i + 1}")
            if not key.exists():
                continue
            log = open(HERE / f"logs_ui_deepseek_p{i}.log", "a", encoding="utf-8")
            p = subprocess.Popen(
                [sys.executable, "-u", "translate_ui_deepseek.py",
                 "--part", str(i), "--parts", str(args.pools),
                 "--batch", "8", "--workers", "2",
                 "--key-file", key.name,
                 "--cache-file", f"work/cache_deepseek_ui_p{i}.json",
                 "--no-final"],
                cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
            procs.append(p)

        for p in procs:
            p.wait()
        print(f"[{time.strftime('%H:%M:%S')}] раунд {rnd} завершён", flush=True)

    print("финальная сборка...", flush=True)
    subprocess.run([sys.executable, "merge_ui_caches.py"], cwd=HERE)
    subprocess.run([sys.executable, "build_tooltip_script.py"], cwd=HERE)
    subprocess.run(["node", "test_tooltip_translator.js",
                    "../kubejs/client_scripts/ru_tooltip_translator.js"], cwd=HERE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
