"""Возвращает наш перевод после теста перевода сообщества.

Откатывает всё, что заменил install_community_translation.py:
  * квесты, экраны классов, lang-файлы kubejs, lang механизмов;
  * options.txt и linggango-resourcepacks.toml (с нашим паком последним);
  * убирает их ресурспак из списка.

Запуск:
    python3 restore_our_translation.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE  # noqa: E402

HERE = Path(__file__).parent
BACKUP = HERE / "backup" / "our_translation_cf"


def restore_dir(rel: str) -> None:
    src = BACKUP / rel
    dst = INSTANCE / rel
    if not src.exists():
        print(f"  нет бэкапа: {rel}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"  восстановлено: {rel} ({sum(1 for _ in dst.rglob('*') if _.is_file())} файлов)")


def main() -> int:
    if not BACKUP.exists():
        raise SystemExit(f"нет бэкапа {BACKUP}")
    print("=== возвращаем наш перевод")
    for rel in ("config/ftbquests/quests", "config/class_enhancement/classes",
                "kubejs/assets/enchdesc/lang", "kubejs/assets/ftbquests/lang",
                "kubejs/assets/ftbquestlocalizer/lang"):
        restore_dir(rel)
    for rel in ("config/linggango_machinery/pack/assets/linggango_tweaks/lang/en_us.json",
                "options.txt", "config/linggango-resourcepacks.toml"):
        src = BACKUP / rel
        if src.exists():
            dst = INSTANCE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  восстановлено: {rel}")
    # их пак убираем из списков, файл можно оставить
    for rel, prefix, entry in (
            ("options.txt", "resourcePacks:", '"file/Community_RussianTranslations.zip"'),
            ("config/linggango-resourcepacks.toml", "packs = ",
             '"file/Community_RussianTranslations.zip"')):
        p = INSTANCE / rel
        if not p.exists():
            continue
        import re
        text = p.read_text(encoding="utf-8")
        m = re.search(re.escape(prefix) + r"\[(.*?)\]", text, flags=re.S)
        if not m:
            continue
        items = [it.strip() for it in m.group(1).split(",") if it.strip() and it.strip() != entry]
        p.write_text(text[:m.start(1)] + ", ".join(items) + text[m.end(1):], encoding="utf-8")
        print(f"  их пак убран из {rel}")
    print("\nнаш перевод снова в сборке")
    return 0


if __name__ == "__main__":
    sys.exit(main())
