"""Ставит перевод сообщества (CommunityRussianTranslation.zip) в сборку.

Нужен, чтобы сравнить их перевод с нашим прямо в игре. Наш перевод перед этим
откладывается в backup/our_translation_cf/ — вернуть его можно одной командой:

    python3 restore_our_translation.py

Что ставится (как есть, без правок):
  * config/ftbquests/quests/**          — их квесты (LGQ1, тот же ключ)
  * kubejs/assets/*/lang/ru_ru.json     — их lang-файлы kubejs
  * config/class_enhancement/classes/    — их экраны классов (translate-ключи)
  * resourcepacks/Community_RussianTranslations.zip — их ресурспак (регистрируется
    последним, чтобы перекрывать наш по общим модам)

ВАЖНО: их квесты содержат ключи-заглушки (ftbquests.chapter....), которые
разворачивает аддон ftbquestlocalizer. Без этого аддона в игре будут ключи
вместо текста — сам перевод при этом никуда не девается, он в их ru_ru.json.

Запуск:
    python3 install_community_translation.py
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paths import INSTANCE  # noqa: E402

HERE = Path(__file__).parent
BACKUP = HERE / "backup" / "our_translation_cf"
# архив лежит в корне «Для сборок переводов» (на уровень выше linggango/)
SRC_ZIP = HERE.parent.parent / "CommunityRussianTranslation.zip"
PACK_ENTRY = "resourcepacks/Community_RussianTranslations.zip"


def backup_dir(rel: str) -> Path:
    dst = BACKUP / rel
    if dst.exists():
        shutil.rmtree(dst)
    src = INSTANCE / rel
    if src.exists():
        shutil.copytree(src, dst)
        print(f"  сохранено: {rel} ({sum(1 for _ in dst.rglob('*') if _.is_file())} файлов)")
    return dst


def put_last(text: str, prefix: str, entry: str) -> str:
    import re
    m = re.search(re.escape(prefix) + r"\[(.*?)\]", text, flags=re.S)
    if not m:
        return text
    items = [it.strip() for it in m.group(1).split(",") if it.strip()]
    items = [it for it in items if it != entry]
    items.append(entry)
    return text[:m.start(1)] + ", ".join(items) + text[m.end(1):]


def main() -> int:
    if not SRC_ZIP.exists():
        raise SystemExit(f"нет файла: {SRC_ZIP}")
    print("=== 1. откладываем наш перевод в бэкап")
    for rel in ("config/ftbquests/quests", "config/class_enhancement/classes",
                "kubejs/assets/enchdesc/lang", "kubejs/assets/ftbquests/lang",
                "kubejs/assets/ftbquestlocalizer/lang"):
        backup_dir(rel)
    for rel in ("config/linggango_machinery/pack/assets/linggango_tweaks/lang/en_us.json",
                "options.txt", "config/linggango-resourcepacks.toml"):
        src = INSTANCE / rel
        if src.exists():
            dst = BACKUP / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  сохранено: {rel}")

    tmp = Path("/tmp/community_tr")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(SRC_ZIP) as z:
        z.extractall(tmp)
    print("=== 2. ставим их файлы")

    # квесты
    src_quests = tmp / "config/ftbquests/quests"
    dst_quests = INSTANCE / "config/ftbquests/quests"
    if dst_quests.exists():
        shutil.rmtree(dst_quests)
    shutil.copytree(src_quests, dst_quests)
    print(f"  квесты: {sum(1 for _ in dst_quests.rglob('*.snbt'))} .snbt")

    # lang-файлы kubejs
    for ns in ("enchdesc", "ftbquests", "ftbquestlocalizer"):
        src = tmp / f"kubejs/assets/{ns}/lang/ru_ru.json"
        if src.exists():
            dst = INSTANCE / f"kubejs/assets/{ns}/lang/ru_ru.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  kubejs/assets/{ns}/lang/ru_ru.json")

    # экраны классов
    src_cls = tmp / "config/class_enhancement/classes"
    dst_cls = INSTANCE / "config/class_enhancement/classes"
    if dst_cls.exists():
        shutil.rmtree(dst_cls)
    shutil.copytree(src_cls, dst_cls)
    print(f"  class_enhancement: {sum(1 for _ in dst_cls.glob('*.json'))} классов")

    # их ресурспак
    pack_src = tmp / PACK_ENTRY
    pack_dst = INSTANCE / "resourcepacks/Community_RussianTranslations.zip"
    shutil.copy2(pack_src, pack_dst)
    print(f"  ресурспак: {pack_dst.name} ({pack_dst.stat().st_size // 1024} КБ)")

    # регистрируем их пак последним (после нашего)
    entry = '"file/Community_RussianTranslations.zip"'
    toml = INSTANCE / "config/linggango-resourcepacks.toml"
    text = toml.read_text(encoding="utf-8")
    toml.write_text(put_last(text, "packs = ", entry), encoding="utf-8")
    opts = INSTANCE / "options.txt"
    otext = opts.read_text(encoding="utf-8")
    opts.write_text(put_last(otext, "resourcePacks:", entry), encoding="utf-8")
    print("  их пак зарегистрирован последним в options.txt и linggango-resourcepacks.toml")

    print("\nготово. их перевод установлен, наш отложен в",
          BACKUP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
