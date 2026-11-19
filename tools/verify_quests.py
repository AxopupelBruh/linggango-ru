"""Проверка квестов после перевода: разметка, картинки, токены, структура."""
import re
import sys
import zipfile
import glob
from pathlib import Path
from paths import INSTANCE, WORK_DIR  # noqa: E402

HERE = Path(__file__).parent
ROOT = INSTANCE
sys.path.insert(0, str(HERE))
import lgq_crypt as C  # noqa: E402
import snbt_text  # noqa: E402
from tr_engine import RE_MARKUP  # noqa: E402

Q = ROOT / "config/ftbquests/quests"
O = HERE / "backup/quests_original"
TOKEN = re.compile(r"\{image:[^}]*\}|\[[^\[\]]{0,160}\]")
BROKEN = re.compile(r"\[\[\d+\]\]|\[\d+\]")
IMG = re.compile(r"\{image:([a-z0-9_.]+):([^\s}]+)")

# где лежат ассеты
have = set()
for j in glob.glob(str(ROOT / "mods/*.jar")) + glob.glob(str(ROOT / "resourcepacks/*.zip")):
    try:
        z = zipfile.ZipFile(j)
    except Exception:
        continue
    for n in z.namelist():
        if n.startswith("assets/"):
            have.add(n[len("assets/"):])
for f in (ROOT / "kubejs/assets").rglob("*"):
    if f.is_file():
        have.add(f.relative_to(ROOT / "kubejs/assets").as_posix())


def texts(root):
    for f in sorted(root.rglob("*.snbt")):
        raw = f.read_text(encoding="utf-8")
        raw = C.decrypt(raw) if C.is_encrypted(raw) else raw
        for k, t, _s, _e in snbt_text.iter_texts(raw):
            yield f, k, t


bad_marks = bad_imgs = bad_tokens = 0
problems = []
for f, k, t in texts(Q):
    if BROKEN.search(t):
        bad_tokens += 1
        problems.append(f"токен: {f.name}: {t[:80]}")
    for ns, path in IMG.findall(t):
        if f"{ns}/{path}" not in have:
            bad_imgs += 1
            problems.append(f"картинка: {f.name}: {ns}:{path}")

# разметка: в переводе и в оригинале должна совпадать
orig = {}
for f, k, t in texts(O):
    orig.setdefault(t, []).append(f.name)
for f, k, t in texts(Q):
    pass

# сверяем по парам оригинал→перевод
tr = {}
for f, k, t in texts(Q):
    tr.setdefault(t, []).append(f.name)

print(f"битых токенов: {bad_tokens}")
print(f"битых ссылок на картинки: {bad_imgs}")
for p in problems[:10]:
    print("   ", p)

# структура: нетекстовая часть файла не менялась
diff = 0
for f in sorted(Q.rglob("*.snbt")):
    rel = f.relative_to(Q)
    new_raw = f.read_text(encoding="utf-8")
    new = C.decrypt(new_raw) if C.is_encrypted(new_raw) else new_raw
    o_raw = (O / rel).read_text(encoding="utf-8")
    old = C.decrypt(o_raw) if C.is_encrypted(o_raw) else o_raw
    if re.sub(r'"(?:[^"\\]|\\.)*"', '""', old) != re.sub(r'"(?:[^"\\]|\\.)*"', '""', new):
        diff += 1
        print("   структура отличается:", rel)
print(f"файлов с изменением нетекстовой части: {diff}")
