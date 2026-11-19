"""Сравнивает стратегии подстановки терминов на реальных строках квестов."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tr_engine import DeepLBackend, Translator, load_glossary

HERE = Path(__file__).parent
data = json.loads((HERE / "work/quests.json").read_text(encoding="utf-8"))
items = list(data.items())[:30]
gl = load_glossary()
key = (HERE / ".deepl_key").read_text(encoding="utf-8").strip()

out = {}
for mode in ("token", "mixed"):
    tr = Translator(DeepLBackend(key), gl, cache_path=HERE / f"cmp_{mode}.json", mode=mode)
    for src, where in items:
        out.setdefault(src, {})[mode] = tr.translate(src)
(HERE / "cmp_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for src, v in list(out.items()):
    print(f"\nEN: {src[:150]}")
    print(f"  token: {v['token'][:150]}")
    print(f"  mixed: {v['mixed'][:150]}")
