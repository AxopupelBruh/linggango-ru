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
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = INSTANCE
# локальная копия репозитория, в который выкладывается релиз
STAGE = Path("/home/ax/Documents/Opencode/Для сборок переводов/github-archive/linggango-ru")
REPO = "AxopupelBruh/linggango-ru"

# документы по переводу лежат рядом с рабочим каталогом
DOCS = HERE.parent / "docs"
PROMPT_SRC = DOCS / "ПРОМТ_СИСТЕМНЫЙ_EN_RU.txt"

# что копируем: (источник, назначение внутри релиза)
FILES = [
    (ROOT / "resourcepacks/zz_linggango_ru.zip", "install/resourcepacks/zz_linggango_ru.zip"),
    (ROOT / "kubejs/client_scripts/ru_tooltip_translator.js",
     "install/kubejs/client_scripts/ru_tooltip_translator.js"),
    (ROOT / "mods/zz_linggango_ru_books.jar", "install/mods/zz_linggango_ru_books.jar"),
    (DOCS / "ГАЙД_ЛОКАЛИЗАЦИИ.md", "docs/LOCALIZATION_GUIDE.md"),
    (DOCS / "LINGGANGO_TRANSLATION_PLAN.md", "docs/TRANSLATION_PLAN.md"),
    (HERE / "release/README.md", "README.md"),
    (HERE / "release/gitignore", ".gitignore"),
]

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

# скрипты: в релиз идут только рабочие, без одноразовых правок.
# Список — замыкание конвейера (reapply_translation.py и его шаги, сборка релиза,
# проверки) плюс всё, на что ссылаются docs/ репозитория.
TOOL_KEEP = (
    "apply_act_titles.py", "apply_extra.py", "apply_kubejs.py",
    "apply_machinery_lang.py", "apply_manual_round4.py", "apply_quests.py",
    "audit_case.py", "audit_font_coverage.py", "audit_terms.py",
    "brands.py", "build_glossary.py", "build_png_gallery.py",
    "build_resourcepack.py", "build_tooltip_script.py", "classfile.py",
    "cleanup_brands.py", "collect.py", "collect_extra.py",
    "collect_fix_targets.py", "collect_quest_png.py", "collect_text_png.py",
    "compare_github.py", "deepl_backend.py", "deepseek_backend.py",
    "deepseek_driver.py", "dump_plain.py", "extract_quests.py",
    "fill_lang_gap.py", "fix_books.py", "fix_case.py", "fix_java_strings.py",
    "fix_patchouli.py", "fix_patchouli_labels.py", "fix_translate.py",
    "fix_ui_brands.py", "fix_zwnj.py", "fixup.py", "ftbq_parse.py",
    "gemini_backend.py", "install_community_translation.py", "lang_json.py",
    "lgq_crypt.py", "manual_extra.py", "manual_fixes.py",
    "manual_github_merge.py", "manual_machines.py", "merge_ui_caches.py",
    "normalize_terms.py", "paths.py", "polish_ru.py", "publish_release.py",
    "reapply_translation.py", "repair_markup.py",
    "restore_our_translation.py", "run.py", "scan_java_strings.py",
    "scan_ui_strings.py", "snbt_text.py", "sync_books_datapack.py",
    "tr_engine.py", "translate_runtime_missing.py", "translate_ui_deepseek.py",
    "verify.py", "verify_all.py", "verify_pack.py", "verify_quests.py",
)

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
    for name in TOOL_KEEP:
        p = HERE / name
        if not p.exists():
            print(f"  НЕТ tools/{name}")
            continue
        shutil.copy2(p, tools_dir / name)
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


DEFAULT_MSG = "Liggango: полный перевод сборки на русский"


def push(message: str = DEFAULT_MSG) -> None:
    def run(*args: str) -> None:
        subprocess.run(args, cwd=STAGE, check=True)

    if not (STAGE / ".git").exists():
        run("git", "init", "-b", "main")
    run("git", "add", "-A")
    run("git", "commit", "-m", message)
    run("git", "push", "-u", "origin", "main")


if __name__ == "__main__":
    build()
    if "--push" in sys.argv:
        msg = sys.argv[sys.argv.index("--msg") + 1] if "--msg" in sys.argv else DEFAULT_MSG
        push(msg)
