"""Выгружает все зашифрованные квесты в открытом виде (для правки и пересборки).

Источник по умолчанию — ``backup/quests_original`` (оригиналы до перевода):
в инстансе лежат уже переведённые квесты, и выгрузка из него дала бы русский
текст вместо английского оригинала, который нужен для сверки и сбора строк.

    python3 dump_plain.py              # из backup/quests_original
    python3 dump_plain.py --instance   # из инстанса (текущее состояние игры)
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import lgq_crypt as C
from paths import BACKUP, INSTANCE  # noqa: E402

PLAIN = Path(__file__).parent / "plain"

ap = argparse.ArgumentParser(description="выгрузка квестов FTB в открытом виде")
ap.add_argument("--instance", action="store_true",
                help="брать квесты из инстанса, а не из backup/quests_original")
ap.add_argument("--out", default=str(PLAIN), help="куда складывать (по умолчанию ./plain)")
args = ap.parse_args()

if args.instance:
    source, quests = "инстанс", INSTANCE / "config/ftbquests/quests"
else:
    source, quests = "backup/quests_original", BACKUP / "quests_original"

if not quests.exists():
    sys.exit(f"нет источника квестов: {quests}")

out_dir = Path(args.out)
n = 0
for f in sorted(quests.rglob("*.snbt")):
    raw = f.read_text(encoding="utf-8")
    if C.is_encrypted(raw):
        raw = C.decrypt(raw)
    out = out_dir / f.relative_to(quests)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(raw, encoding="utf-8")
    n += 1
print(f"выгружено {n} файлов из «{source}» в {out_dir}")
