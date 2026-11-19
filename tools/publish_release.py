"""Сборка релиза перевода Linggango в отдельную папку для публикации на GitHub.

Берёт из инстанса только то, что относится к переводу, и раскладывает в
структуру, повторяющую раскладку сборки:

    install/<путь>   — копируется в корень инстанса как есть
    data/            — итоговые словари переводов (json)
    tools/           — скрипты, которыми перевод сделан
    docs/            — гайд и план перевода

Жёстко исключены (никогда не попадают в репозиторий):
    ключи API (*.deepl_key*, *.deepseek_key*, *.gemini_key*),
    venv/, __pycache__/, backup/, pack_build/, кэши переводов (*cache_*.json),
    промежуточные дампы (plain/), work/*.bak

Запуск:
    python3 publish_release.py            # только собрать папку
    python3 publish_release.py --push     # собрать и залить в GitHub
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STAGE = Path("/home/ax/Documents/Opencode/deepl/linggango-ru")
REPO = "AxopupelBruh/linggango-ru"

# что копируем: (источник, назначение внутри релиза)
FILES = [
    (ROOT / "resourcepacks/zz_linggango_ru.zip", "install/resourcepacks/zz_linggango_ru.zip"),
    (ROOT / "kubejs/client_scripts/ru_tooltip_translator.js",
     "install/kubejs/client_scripts/ru_tooltip_translator.js"),
    (ROOT / "mods/zz_linggango_ru_books.jar", "install/mods/zz_linggango_ru_books.jar"),
    (ROOT / "ГАЙД_ЛОКАЛИЗАЦИИ.md", "docs/LOCALIZATION_GUIDE.md"),
    (ROOT / "LINGGANGO_TRANSLATION_PLAN.md", "docs/TRANSLATION_PLAN.md"),
    (HERE / "release/README.md", "README.md"),
    (HERE / "release/gitignore", ".gitignore"),
]

# системный промт переводчика — лежит в общей папке гайдов
PROMPT_SRC = Path("/home/ax/Documents/Opencode/Для сборок переводов/ПРОМТ_СИСТЕМНЫЙ_EN_RU.txt")

DIRS = [
    (ROOT / "datapacks/zz_linggango_ru_books", "install/datapacks/zz_linggango_ru_books"),
    (ROOT / "config/ftbquests/quests", "install/config/ftbquests/quests"),
]

# итоговые словари
DICTS = [
    "mods_ru.json", "quests_ru.json", "patchouli_ru.json", "ui_strings_ru.json",
    "pack_script_ru.json", "terms_merged.json", "vanilla_ru_ru.json",
    "extra_ru.json", "runtime_missing_ru.json", "runtime_manual_ru.json",
    "ui_strings_manual_ru.json",
]

# скрипты
TOOL_SKIP = {"generated_ru_tooltip_translator.js"}


def copy(src: Path, rel: str, base: Path) -> int:
    dst = base / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        return sum(1 for _ in dst.rglob("*") if _.is_file())
    shutil.copy2(src, dst)
    return 1


def build() -> None:
    # собираем во временную папку, чтобы не снести .git в STAGE
    tmp = Path(tempfile.mkdtemp(prefix="linggango-rel-"))
    try:
        _build_into(tmp)
        if STAGE.exists():
            for child in STAGE.iterdir():
                if child.name == ".git":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        else:
            STAGE.mkdir(parents=True)
        for child in tmp.iterdir():
            dst = STAGE / child.name
            if child.is_dir():
                shutil.copytree(child, dst)
            else:
                shutil.copy2(child, dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _build_into(stage: Path) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    n = 0
    for src, rel in FILES:
        if not src.exists():
            print(f"  НЕТ {src}")
            continue
        n += copy(src, rel, stage)
        print(f"  {rel}")
    for src, rel in DIRS:
        if not src.exists():
            print(f"  НЕТ {src}")
            continue
        n += copy(src, rel, stage)
        print(f"  {rel}/ ({sum(1 for _ in (stage/rel).rglob('*') if _.is_file())} файлов)")
    for d in DICTS:
        p = HERE / "work" / d
        if p.exists():
            n += copy(p, f"data/{d}", stage)
            print(f"  data/{d}")
    if PROMPT_SRC.exists():
        n += copy(PROMPT_SRC, "docs/SYSTEM_PROMPT_EN_RU.txt", stage)
        print("  docs/SYSTEM_PROMPT_EN_RU.txt")
    tools_dir = stage / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(HERE.glob("*.py")):
        if p.name.startswith("_"):
            continue
        shutil.copy2(p, tools_dir / p.name)
        n += 1
    for p in sorted(HERE.glob("*.js")):
        if p.name in TOOL_SKIP:
            continue
        shutil.copy2(p, tools_dir / p.name)
        n += 1
    print(f"  tools/ ({len(list(tools_dir.iterdir()))} скриптов)")
    print(f"\nвсего файлов: {n}")

    # проверка на секреты
    bad = [p for p in stage.rglob("*") if p.is_file() and (
        "key" in p.name.lower() or p.suffix in (".env", ".pem"))]
    if bad:
        raise SystemExit(f"ВНИМАНИЕ: в релизе есть подозрительные файлы: {bad}")
    print("секретов в релизе нет")


def push() -> None:
    def run(*args: str) -> None:
        subprocess.run(args, cwd=STAGE, check=True)

    if not (STAGE / ".git").exists():
        run("git", "init", "-b", "main")
    run("git", "add", "-A")
    run("git", "-c", "user.name=AxopupelBruh",
        "-c", "user.email=306857641+AxopupelBruh@users.noreply.github.com",
        "commit", "-m", "Liggango: полный перевод сборки на русский")
    run("git", "push", "-u", "origin", "main")


if __name__ == "__main__":
    build()
    if "--push" in sys.argv:
        push()
