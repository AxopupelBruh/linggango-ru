"""Итоговая проверка перевода сборки Linggango."""
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lgq_crypt as C  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parent
CYR = re.compile(r"[Ѐ-ӿ]")

print("=" * 70)
print("ПРОВЕРКА ПЕРЕВОДА СБОРКИ LINGGANGO")
print("=" * 70)

# 1. Квесты
QUESTS = ROOT / "config/ftbquests/quests"
files = sorted(QUESTS.rglob("*.snbt"))
enc = sum(1 for f in files if C.is_encrypted(f.read_text(encoding="utf-8")))
ru_titles = total_titles = 0
broken = []
for f in files:
    raw = f.read_text(encoding="utf-8")
    try:
        plain = C.decrypt(raw) if C.is_encrypted(raw) else raw
    except Exception as exc:
        broken.append((f.name, str(exc)))
        continue
    for m in re.finditer(r'^\s*(?:title|subtitle):\s*"((?:[^"\\]|\\.)*)"', plain, re.M):
        total_titles += 1
        if CYR.search(m.group(1)):
            ru_titles += 1
print(f"\n[Квесты] файлов: {len(files)}, зашифровано: {enc}, повреждённых: {len(broken)}")
print(f"        заголовков/подзаголовков: {total_titles}, с кириллицей: {ru_titles} "
      f"({ru_titles * 100 // max(total_titles, 1)}%)")

# 2. Ресурспак
zp = ROOT / "resourcepacks/zz_linggango_ru.zip"
with zipfile.ZipFile(zp) as z:
    names = z.namelist()
    langs = [n for n in names if n.endswith("/lang/ru_ru.json")]
    books = [n for n in names if "/patchouli_books/" in n]
    keys = 0
    ru_keys = 0
    for n in langs:
        d = json.loads(z.read(n).decode("utf-8"))
        keys += len(d)
        ru_keys += sum(1 for v in d.values() if isinstance(v, str) and CYR.search(v))
    mcmeta = json.loads(z.read("pack.mcmeta").decode("utf-8"))
print(f"\n[Ресурспак] {zp.name}: {len(names)} файлов, {len(langs)} lang-файлов, "
      f"{len(books)} файлов книг")
print(f"           ключей: {keys}, с кириллицей: {ru_keys} "
      f"({ru_keys * 100 // max(keys, 1)}%)")
print(f"           pack_format: {mcmeta['pack']['pack_format']}")

# 3. KubeJS
kj = []
for f in sorted((ROOT / "kubejs/assets").glob("*/lang/ru_ru.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    kj.append((f.parent.parent.name, len(d)))
lang_js = (ROOT / "kubejs/client_scripts/lang.js").read_text(encoding="utf-8")
ru_block = re.search(r'ClientEvents\.lang\("ru_ru"(.*?)\n\}\);', lang_js, re.S)
ru_lines = len(re.findall(r"event\.(renameItem|add)\(", ru_block.group(1))) if ru_block else 0
print(f"\n[KubeJS] ru_ru.json: {sum(k for _, k in kj)} ключей в {len(kj)} файлах")
print(f"         блок ru_ru в lang.js: {ru_lines} строк")

# 4. Что осталось на английском
left = []
for src in ("quests", "mods", "patchouli", "kubejs"):
    p = HERE / "work" / f"{src}_ru.json"
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    same = sum(1 for k, v in d.items() if v == k and re.search(r"[A-Za-z]{3}", k))
    left.append((src, len(d), same))
print("\n[Осталось на английском]")
for src, total, same in left:
    print(f"  {src:11s} {same:5d} из {total:6d} ({same * 100 // max(total, 1)}%)")
print("  (это названия модов, внутренние ID и шуточные строки — в игре они английские)")

# 5. Приоритет ресурспака
toml = (ROOT / "config/linggango-resourcepacks.toml").read_text(encoding="utf-8")
m = re.search(r'packs = \[(.*?)\]', toml, re.S)
items = [x.strip() for x in m.group(1).split(",") if x.strip()]
print(f"\n[Приоритет] наш пак в toml: позиция {items.index(chr(34) + 'file/zz_linggango_ru.zip' + chr(34)) + 1} "
      f"из {len(items)} (последний = высший приоритет)")
print(f"             в options.txt: {'есть' if 'file/zz_linggango_ru.zip' in (ROOT / 'options.txt').read_text(encoding='utf-8') else 'НЕТ'}")
print("=" * 70)
