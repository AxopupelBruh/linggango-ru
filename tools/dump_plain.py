"""Выгружает все зашифрованные квесты в открытом виде (для правки и пересборки)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import lgq_crypt as C
from paths import INSTANCE  # noqa: E402

QUESTS = INSTANCE / "config/ftbquests/quests"
PLAIN = Path(__file__).parent / "plain"

n = 0
for f in sorted(QUESTS.rglob("*.snbt")):
    raw = f.read_text(encoding="utf-8")
    if C.is_encrypted(raw):
        raw = C.decrypt(raw)
    out = PLAIN / f.relative_to(QUESTS)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(raw, encoding="utf-8")
    n += 1
print(f"выгружено {n} файлов в {PLAIN}")
