# -*- coding: utf-8 -*-
"""Финальный аудит переводов Linggango: ищем строки, где русский текст в паке
не соответствует английскому оригиналу того же ключа.

Сигналы:
  dup    — в паке стоит перевод, который наш глоссарий даёт ДЛЯ ДРУГОЙ строки
  num    — числа не совпадают с оригиналом
  ph     — не совпадают %-плейсхолдеры
  trunc  — перевод обрезан
  term   — терминологическое противоречие (в оригинале «блок», в переводе «слиток»)
"""
import zipfile, json, os, re, collections, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_terms import build_terms, MANUAL

INST = "/home/ax/.local/share/gdlauncher_carbon/data/instances/Linggango/instance"
WS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")
PACK = os.path.join(INST, "resourcepacks", "zz_linggango_ru.zip")

FMT = re.compile(r"§[0-9a-fk-orA-FK-OR]")
NUMRX = re.compile(r"\d+(?:[.,]\d+)*")
PH_RX = re.compile(r"%(?:\d+\$)?[sd]|%%|\{[^}]*\}|\$\([^)]*\)")
ENW = re.compile(r"[A-Za-z][A-Za-z'\-]*")
RUW = re.compile(r"[а-яё][а-яё\-]*", re.I)


THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def _num(m):
    s = m.group(0)
    if THOUSANDS.fullmatch(s):           # 1,000 -> 1000 (разделитель тысяч)
        s = s.replace(",", "")
    elif re.fullmatch(r"\d+,\d{1,2}", s):  # 0,5 -> 0.5 (десятичная запятая)
        s = s.replace(",", ".")
    elif "," in s:
        s = s.replace(",", "")
    if "." in s:
        a, b = s.split(".", 1)
        b = b.rstrip("0")
        s = (a.lstrip("0") or "0") + ("." + b if b else "")
    else:
        s = s.lstrip("0") or "0"
    return s


def norm(t):
    if not isinstance(t, str):
        return None
    t = FMT.sub("", t).replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return NUMRX.sub(_num, t).lower()


def nums(t):
    return sorted(_num(m) for m in NUMRX.finditer(FMT.sub("", t or "")))


def phs(t):
    return sorted(re.sub(r"^\d+\$", "", p) for p in PH_RX.findall(t or ""))


def rjz(z, n):
    try:
        return json.loads(z.read(n).decode("utf-8"))
    except Exception:
        return None


SYN = [
    {"cyan", "light blue", "azure"}, {"gray", "grey"}, {"magenta", "pink"},
    {"light gray", "light grey"}, {"dark gray", "dark grey"},
    {"redstone", "red dust"}, {"golden apple", "gold apple"},
]
ORDINAL = re.compile(r"\b\d+(st|nd|rd|th)\b", re.I)


def syn_pair(a, b):
    for grp in SYN:
        if a in grp and b in grp:
            return True
    return False


def content_words(t):
    stop = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "for", "with",
            "from", "is", "are", "was", "were", "be", "it", "its", "as", "by", "your",
            "this", "that", "when", "while", "not", "no", "you", "all", "s"}
    return {w.lower() for w in ENW.findall(t)} - stop


terms = build_terms()
terms.update(MANUAL)
term_ru2en = collections.defaultdict(set)
for w, r in terms.items():
    term_ru2en[r].add(w)

en_ord = collections.defaultdict(dict)
ru_ord = collections.defaultdict(dict)
for fn in sorted(os.listdir(os.path.join(INST, "mods"))):
    if not fn.endswith(".jar"):
        continue
    try:
        z = zipfile.ZipFile(os.path.join(INST, "mods", fn))
    except Exception:
        continue
    names = z.namelist()
    for n in names:
        if not n.startswith("assets/") or not n.endswith("/lang/en_us.json"):
            continue
        ns = n.split("/")[1]
        d = rjz(z, n)
        if not d:
            continue
        en_ord[ns].update(d)
        rp = n.replace("/en_us.json", "/ru_ru.json")
        if rp in names:
            rd = rjz(z, rp)
            if rd:
                ru_ord[ns].update(rd)

ours = json.loads(open(f"{WS}/work/mods_ru.json", encoding="utf-8").read())
mploc = json.load(open(f"{WS}/work/mploc_ru.json", encoding="utf-8"))

pack = {}
with zipfile.ZipFile(PACK) as z:
    for n in z.namelist():
        if n.startswith("assets/") and n.endswith("/lang/ru_ru.json"):
            pack[n.split("/")[1]] = rjz(z, n) or {}

findings = []
for ns, ru_all in pack.items():
    en = en_ord.get(ns, {})
    if not en:
        continue
    mod_ru = ru_ord.get(ns, {})
    mp_ns = mploc.get(ns, {}) if isinstance(mploc, dict) else {}

    our2en = collections.defaultdict(set)
    for k2, e2 in en.items():
        o2 = ours.get(e2)
        if isinstance(o2, str) and norm(o2):
            our2en[norm(o2)].add(e2)

    for key, ru in ru_all.items():
        if not isinstance(ru, str) or not ru.strip():
            continue
        e = en.get(key)
        if e is None:
            continue
        nr, ne = norm(ru), norm(e)
        if nr == ne:
            continue

        sig = []
        score = 0

        # --- перевод от другого ключа ---
        owners = our2en.get(nr)
        if owners:
            e_cw = content_words(e)
            for o in owners:
                if norm(o) == ne:
                    continue
                o_cw = content_words(o)
                if e_cw and o_cw and len(e_cw & o_cw) / max(len(e_cw), len(o_cw)) >= 0.5:
                    continue          # тот же смысл, разная формулировка
                if syn_pair(e.strip().lower(), o.strip().lower()):
                    continue          # синонимы
                score += 85
                sig.append(f"перевод строки {o[:70]!r}")
                break

        # --- числа ---
        nn, ne_n = nums(ru), nums(e)
        if nn != ne_n and ne_n and nn and not ORDINAL.search(e):
            score += 90
            sig.append(f"числа: EN {ne_n} vs RU {nn}")

        # --- плейсхолдеры ---
        pp, pe = phs(ru), phs(e)
        if pp != pe:
            score += 90
            sig.append(f"плейсхолдеры: EN {pe} vs RU {pp}")

        # --- обрыв ---
        ratio = len(ru.strip()) / max(len(e.strip()), 1)
        if (ratio < 0.4 and len(e.strip()) >= 25 and "..." not in ru and "…" not in ru
                and not e.strip().endswith(("!", "?"))):
            score += 80
            sig.append(f"обрыв: {ratio:.2f} от оригинала")

        # --- терминологическое противоречие ---
        e_all = {w.lower() for w in ENW.findall(e)}
        e_terms = e_all & set(MANUAL)
        ru_words = [w.lower() for w in RUW.findall(ru)]
        if e_terms:
            def has_term(r):
                stem = r[:max(4, len(r) - 2)]
                return any(w.startswith(stem) for w in ru_words)
            ru_terms = {r for r in MANUAL.values() if len(r) >= 4 and any(
                w == r for w in ru_words)}
            for W in e_terms:
                exp = MANUAL[W]
                if has_term(exp):
                    continue
                for R in sorted(ru_terms):
                    cands = {w for w, rr in MANUAL.items() if rr == R}
                    if len(cands) != 1:
                        continue
                    W2 = next(iter(cands))
                    if W2 in e_all:
                        continue
                    score += 95
                    sig.append(f"термин: EN «{W}» ({exp}) → в переводе «{R}» ({W2})")
                    break
                else:
                    continue
                break

        if score >= 80:
            mpr = mp_ns.get(key)
            src = ""
            if isinstance(mpr, str) and norm(mpr) == nr:
                src = "MPLOC"
            elif isinstance(mod_ru.get(key), str) and norm(mod_ru[key]) == nr:
                src = "мод"
            findings.append(dict(score=score, ns=ns, key=key, en=e, ru=ru,
                                 our=ours.get(e) if isinstance(ours.get(e), str) else None,
                                 src=src, why=sig))

findings.sort(key=lambda d: (-d["score"], d["ns"], d["key"]))
print(f"терминов: {len(terms)}  кандидатов: {len(findings)}")
for ns, c in collections.Counter(d["ns"] for d in findings).most_common(25):
    print(f"   {ns:<28} {c}")
json.dump(findings, open("/tmp/findings_final.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("→ /tmp/findings_final.json")
