"""Переводит lang-файл механизмов Linggango в конфиге сборки.

Мод linggango_tweaks держит свой ресурспак в
    config/linggango_machinery/pack/assets/linggango_tweaks/lang/en_us.json
и подгружает его сам — наш общий ресурспак эти ключи не перекрывает.
Поэтому перевод пишем прямо в этот файл.

Файл с английским оригиналом копируется в backup/config_extra/ — при повторном
запуске переводится только то, что ещё не переведено (по бэкапу).

Запуск:
    python3 apply_machinery_lang.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE  # noqa: E402
from tr_engine import Translator, load_glossary  # noqa: E402
from deepseek_backend import DeepSeekBackend  # noqa: E402

HERE = Path(__file__).parent
WORK = HERE / "work"
BACKUP = HERE / "backup" / "config_extra"

REL = "config/linggango_machinery/pack/assets/linggango_tweaks/lang/en_us.json"
TARGET = INSTANCE / REL
ORIG = BACKUP / REL


def main() -> int:
    if not TARGET.exists():
        raise SystemExit(f"нет файла: {TARGET}")
    ORIG.parent.mkdir(parents=True, exist_ok=True)
    if not ORIG.exists():
        shutil.copy2(TARGET, ORIG)
        print(f"оригинал сохранён: {ORIG}")

    original = json.loads(ORIG.read_text(encoding="utf-8"))
    current = json.loads(TARGET.read_text(encoding="utf-8"))

    # переводим только те значения, что ещё английские
    todo = {k: v for k, v in original.items()
            if isinstance(v, str) and v.strip() and current.get(k) == v}
    print(f"всего ключей: {len(original)} | ждут перевода: {len(todo)}")
    if not todo:
        print("уже переведено")
        return 0

    glossary = load_glossary()
    key_file = HERE / ".deepseek_key"
    backend = DeepSeekBackend(api_key=key_file.read_text(encoding="utf-8").strip()
                               if key_file.exists() else None)
    backend.max_items = 20
    tr = Translator(backend, glossary, cache_path=WORK / "cache_deepseek_machinery.json")
    sources = list(todo.values())
    out = tr.translate_many(sources)
    tr.cache.save()

    result = dict(current)
    changed = 0
    for src, ru in zip(sources, out):
        if ru.strip():
            for key, val in todo.items():
                if val == src:
                    result[key] = ru
                    changed += 1
    TARGET.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"переведено значений: {changed}")
    for key in list(result)[:5]:
        print(f"   {key} -> {result[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
