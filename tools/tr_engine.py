"""Движок перевода EN→RU для сборки Linggango.

Что делает:
  * защищает форматирование Minecraft (теги <typewriter>, <grad ...>, цвета §/&, hex),
    плейсхолдеры (%s, {0}), ID предметов (minecraft:stone), невидимые символы (U+200C);
  * подставляет термины из глоссария (EN→RU) как защищённые токены — терминология
    едина по всей сборке и совпадает с тем, что игрок видит в игре;
  * переводит пачками через Google Translate (gtx) или DeepL;
  * кэширует переводы по строкам в cache.json — повторные запуски не тратят лимит;
  * валидирует результат: плейсхолдеры на месте, строка не пустая, есть кириллица.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Защита от разрушения
# --------------------------------------------------------------------------

# Форматирование Minecraft: открывающие и закрывающие теги
TAGS = (
    "typewriter|grad|gradient|shadow|wave|click|hover|color|colour|newline|size|"
    "bold|italic|underline|strikethrough|obfuscated|rainbow|transition|keybind|"
    "selector|score|lang|translate|insertion|discriminant|char|sprite|atlas|font|"
    "flip|space|height|offset|advancement|tooltip|br|b"
)
RE_TAG = re.compile(rf"</?(?:{TAGS})(?:\s[^<>]*?)?/?>")
RE_COLOR = re.compile(r"[§&][0-9a-fk-orA-FK-OR]")
RE_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
RE_PLACEHOLDER = re.compile(r"%[-+0-9.#]*[a-zA-Z]|\{\d+\}|\{\}")
RE_URL = re.compile(r"https?://[^\s)\]>]+")
RE_FILE = re.compile(r"\b[\w\-]+\.(?:json|snbt|txt|png|jpg|jpeg|gif|zip)\b")
RE_ID = re.compile(r"\b[a-z][a-z0-9_]*:[a-z0-9_./]+\b")
RE_CMD = re.compile(r"(?<![\w/])/[a-z_]{2,}\b")
RE_INVISIBLE = re.compile("[‌‍⁠﻿‎‏ ]")
# тот же набор, но без обычного пробела: для LLM-бэкендов пробелы маскировать нельзя
RE_INVISIBLE_NOSPACE = re.compile("[‌‍⁠﻿‎‏]")
RE_TOKEN = re.compile(r"\[\[(\d+)\]\]")
RE_GUILLEMET = re.compile("[«»]")
# макросы Patchouli: $(l:ns:path), $(item), $(br), $(crafting_table) — переводить нельзя
RE_PATCHOULI = re.compile(r"\$\([^)]*\)")

# Разметка описаний квестов (мод misanthropyquestadditionsomg + linggango_tweaks).
# Её нельзя переводить: игра сама разбирает эти маркеры.
#   {image:ns:path width:.. height:.. align:..}  — вставка картинки
#   [gap=N]                                    — вертикальный отступ
#   [!tip] [!info] [!danger] [!warning] ...    — выноски
#   [details]…[/details] [spoiler] [center]   — блоки
#   [progress] [progress=HEXID]                — полоса прогресса
#   [item:…] [entity:…] [task:…] [quest:…]     — иконки
#   [link:…] [copy:…] [cmd:…] [hover:…] [key:…] [lang:…]
#   [ff0000]                                   — цвет
RE_MARKUP = re.compile(
    r"\{image:[^}]*\}"
    r"|\[gap=-?\d{1,4}\]"
    r"|\[!(?:tip|info|warn|warning|danger|success|note)\]"
    r"|\[(?:/)?(?:details|spoiler|center)\]"
    r"|\[progress(?:=[0-9a-fA-F]{1,16})?\]"
    r"|\[(?:item|entity|task|quest|link|copy|cmd|hover|key|lang):"
    r"[^\[\]|*]{1,128}(?:\*\d{1,5})?(?:\|[^\[\]]{1,128})?\]"
    r"|\[(?: |x|X|[0-9a-fA-F]{1,16})\]"
)

TOKEN_FMT = "[[{i}]]"


class Protector:
    """Маскирует всё, что нельзя переводить, и подставляет термины глоссария.

    Порядок важен: сначала структура (теги, цвета, ID, невидимые символы),
    потом термины — иначе глоссарий испортит параметры тегов (from=, to=).
    """

    def __init__(self, glossary: dict | None = None, mode: str = "none",
                 token_fmt: str | None = None, keep_spaces: bool = False):
        # glossary: {EN: {"ru": str, "strong": bool}}
        self.token_fmt = token_fmt or TOKEN_FMT
        self.glossary = glossary or {}
        self.mode = mode
        self.keep_spaces = keep_spaces
        self.exact = {}      # en.lower() -> ru
        self.strong = {}     # en.lower() -> ru (подставляются прямо в прозу)
        for en, val in self.glossary.items():
            if isinstance(val, dict):
                ru, strong = val.get("ru"), val.get("strong", False)
            else:
                ru, strong = val, False
            if not ru:
                continue
            # точное совпадение используем только для надёжных (сильных) терминов
            if strong:
                self.exact[en.lower()] = ru
                self.strong[en.lower()] = ru
        self.strong_terms = sorted(self.strong.items(), key=lambda kv: -len(kv[0]))
        self.term_re = None
        if self.strong_terms:
            alts = "|".join(re.escape(t) for t, _ in self.strong_terms)
            self.term_re = re.compile(rf"(?<![\w])({alts})(?![\w])", re.IGNORECASE)

    def lookup_exact(self, text: str) -> str | None:
        """Точное совпадение строки с термином глоссария (название предмета и т.п.)."""
        return self.exact.get(text.strip().lower())

    def protect(self, text: str) -> tuple[str, list[str]]:
        """Возвращает (замаскированный текст, токены для восстановления)."""
        tokens: list[str] = []

        def add_token(value: str) -> str:
            tokens.append(value)
            return self.token_fmt.format(i=len(tokens) - 1)

        # 1. структура — переводить нельзя
        invisible = RE_INVISIBLE_NOSPACE if self.keep_spaces else RE_INVISIBLE
        for rx in (RE_TAG, RE_MARKUP, RE_COLOR, RE_HEX, RE_PLACEHOLDER, RE_URL, RE_FILE, RE_ID,
                   RE_CMD, invisible, RE_GUILLEMET, RE_PATCHOULI):
            text = rx.sub(lambda m: add_token(m.group(0)), text)

        # 2. термины глоссария
        #    mode="token": маскируем токеном и подставляем каноническое название
        #    mode="mixed": вставляем русский термин прямо в английский текст —
        #                   DeepL склоняет его по-русски («Глубокий океан» → «Глубокого океана»)
        if self.term_re and self.mode != "none":
            def repl(m: re.Match) -> str:
                ru = self.strong.get(m.group(0).lower())
                if not ru:
                    return m.group(0)
                return ru if self.mode == "mixed" else add_token(ru)
            text = self.term_re.sub(repl, text)

        return text, tokens

    def restore(self, text: str, tokens: list[str]) -> str:
        pattern = re.escape(self.token_fmt).replace(r"\{i\}", r"(\d+)")
        def repl(m: re.Match) -> str:
            i = int(m.group(1))
            return tokens[i] if i < len(tokens) else m.group(0)
        return re.sub(pattern, repl, text)


# --------------------------------------------------------------------------
# Бэкенды перевода
# --------------------------------------------------------------------------

class GoogleBackend:
    name = "google"
    URL = "https://translate.googleapis.com/translate_a/single"
    max_items = 30
    max_chars = 3500

    def __init__(self, delay: float = 0.35):
        import requests
        self.session = requests.Session()
        self.delay = delay
        self._lock = threading.Lock()
        self._last = 0.0

    def _throttle(self):
        with self._lock:
            gap = time.time() - self._last
            if gap < self.delay:
                time.sleep(self.delay - gap)
            self._last = time.time()

    def translate_batch(self, lines: list[str]) -> list[str]:
        """Переводит список строк одним запросом (разделитель \\n). Возвращает столько же строк."""
        joined = "\n".join(lines)
        out = None
        for attempt in range(6):
            try:
                self._throttle()
                r = self.session.get(
                    self.URL,
                    params={"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": joined},
                    timeout=60,
                )
                if r.status_code == 200:
                    data = r.json()
                    out = "".join(seg[0] for seg in data[0] if seg and seg[0])
                    break
                if r.status_code in (429, 503):
                    if attempt == 5:
                        raise RuntimeError(f"google: HTTP {r.status_code} (лимит)")
                    time.sleep(6 * (attempt + 1))
                    continue
                raise RuntimeError(f"google: HTTP {r.status_code}")
            except Exception as exc:  # noqa: BLE001
                if attempt == 5:
                    raise RuntimeError(f"google не ответил: {exc}") from exc
                time.sleep(5 * (attempt + 1))
        if out is None:
            raise RuntimeError("google: пустой ответ")
        parts = out.split("\n")
        if len(parts) != len(lines):
            # структура поехала — переводим по одной
            return [self.translate_batch([ln])[0] if False else self._single(ln)
                    for ln in lines]
        return parts

    def _single(self, line: str) -> str:
        for attempt in range(6):
            try:
                self._throttle()
                r = self.session.get(
                    self.URL,
                    params={"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": line},
                    timeout=60,
                )
                if r.status_code == 200:
                    data = r.json()
                    return "".join(seg[0] for seg in data[0] if seg and seg[0])
                time.sleep(4 * (attempt + 1))
            except Exception:  # noqa: BLE001
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"google не перевёл строку: {line[:60]!r}")


class DeepLBackend:
    name = "deepl"
    URL_FREE = "https://api-free.deepl.com/v2/translate"
    max_items = 50
    max_chars = 15000
    URL_PRO = "https://api.deepl.com/v2/translate"

    def __init__(self, api_key: str | list[str], formal: bool = False):
        import requests
        keys = [api_key] if isinstance(api_key, str) else list(api_key)
        self.keys = [k.strip() for k in keys if k and k.strip()]
        self.key_index = 0
        self.key = self.keys[0]
        self.url = self.URL_FREE if self.key.endswith(":fx") else self.URL_PRO
        self.session = requests.Session()
        self.formal = formal

    def _rotate_key(self) -> None:
        """Переключаемся на следующий ключ (квота исчерпана)."""
        if self.key_index + 1 < len(self.keys):
            self.key_index += 1
            self.key = self.keys[self.key_index]
            self.url = self.URL_FREE if self.key.endswith(":fx") else self.URL_PRO
            print(f"  → переключаюсь на ключ #{self.key_index + 1}", flush=True)

    def translate_batch(self, lines: list[str]) -> list[str]:
        """Переводит массив строк одним запросом (DeepL принимает text как массив)."""
        out = None
        last_err = ""
        for attempt in range(6):
            try:
                r = self.session.post(
                    self.url,
                    json={
                        "text": lines,
                        "source_lang": "EN",
                        "target_lang": "RU",
                    },
                    headers={
                        "Authorization": f"DeepL-Auth-Key {self.key}",
                        "Content-Type": "application/json",
                    },
                    timeout=90,
                )
                if r.status_code == 200:
                    data = r.json()
                    out = [t["text"] for t in data["translations"]]
                    break
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code == 456:
                    if self.key_index + 1 < len(self.keys):
                        self._rotate_key()
                        continue
                    raise RuntimeError("DeepL: квота исчерпана на всех ключах")
                if r.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                time.sleep(4 * (attempt + 1))
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                if attempt == 5:
                    raise RuntimeError(f"DeepL не ответил: {exc}") from exc
                time.sleep(3 * (attempt + 1))
        if out is None:
            raise RuntimeError(f"DeepL не ответил: {last_err}")
        if len(out) != len(lines):
            raise RuntimeError("DeepL вернул несовпадение числа переводов")
        return out

    def translate_batch_xml(self, lines: list[str], ignore_tags: list[str]) -> list[str]:
        """Перевод с сохранением XML-тегов: DeepL не трогает ignore_tags."""
        out = None
        last_err = ""
        for attempt in range(6):
            try:
                r = self.session.post(
                    self.url,
                    json={
                        "text": lines,
                        "source_lang": "EN",
                        "target_lang": "RU",
                        "tag_handling": "xml",
                        "ignore_tags": ignore_tags,
                    },
                    headers={
                        "Authorization": f"DeepL-Auth-Key {self.key}",
                        "Content-Type": "application/json",
                    },
                    timeout=90,
                )
                if r.status_code == 200:
                    out = [t["text"] for t in r.json()["translations"]]
                    break
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code == 456:
                    if self.key_index + 1 < len(self.keys):
                        self._rotate_key()
                        continue
                    raise RuntimeError("DeepL: квота исчерпана на всех ключах")
                if r.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                time.sleep(4 * (attempt + 1))
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                if attempt == 5:
                    raise RuntimeError(f"DeepL не ответил: {exc}") from exc
                time.sleep(3 * (attempt + 1))
        if out is None:
            raise RuntimeError(f"DeepL не ответил: {last_err}")
        return out

    def usage(self) -> dict:
        r = self.session.get(
            "https://api-free.deepl.com/usage",
            headers={"Authorization": f"DeepL-Auth-Key {self.key}"},
            timeout=30,
        ) if self.url == self.URL_FREE else self.session.get(
            "https://api.deepl.com/usage",
            headers={"Authorization": f"DeepL-Auth-Key {self.key}"},
            timeout=30,
        )
        try:
            return r.json()
        except Exception:  # noqa: BLE001
            return {"raw": r.text[:200]}


# --------------------------------------------------------------------------
# Кэш и переводчик
# --------------------------------------------------------------------------

class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, str] = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self.data = {}
        self._lock = threading.Lock()

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def put_many(self, items: dict[str, str]) -> None:
        with self._lock:
            self.data.update(items)

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=0), encoding="utf-8")
        tmp.replace(self.path)

    def __len__(self) -> int:
        return len(self.data)


class Translator:
    """Переводит строки, кэширует, валидирует, ведёт очередь на ручную правку."""

    def __init__(self, backend, glossary: dict | None = None,
                 cache_path: Path | None = None, mode: str = "none", fixer=None,
                 token_fmt: str | None = None):
        self.backend = backend
        self.protector = Protector(glossary, mode=mode,
                                   token_fmt=token_fmt or TOKEN_FMT)
        self.fixer = fixer
        self.cache = Cache(cache_path or (HERE / "cache.json"))
        self.manual: list[dict] = []
        self.stats = Counter()

    # -- внутреннее ------------------------------------------------------
    def _translate_lines(self, lines: list[str]) -> dict[str, str]:
        """Переводит список уникальных строк, возвращает {исходная: перевод}."""
        cache = self.cache
        todo = [ln for ln in dict.fromkeys(lines) if cache.get(ln) is None]
        if not todo:
            return {ln: self.cache.get(ln) for ln in lines}
        # режем на батчи по лимитам бэкенда
        max_items = getattr(self.backend, "max_items", 30)
        max_chars = getattr(self.backend, "max_chars", 3500)
        batches, cur, cur_len = [], [], 0
        for ln in todo:
            if cur and (len(cur) >= max_items or cur_len + len(ln) > max_chars):
                batches.append(cur)
                cur, cur_len = [], 0
            cur.append(ln)
            cur_len += len(ln) + 1
        if cur:
            batches.append(cur)
        done = 0
        for batch in batches:
            try:
                translated = self.backend.translate_batch(batch)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! батч не удался ({exc}); пробуем построчно", flush=True)
                translated = []
                for line in batch:
                    try:
                        translated.append(self.backend.translate_batch([line])[0])
                    except Exception:  # noqa: BLE001
                        translated.append(line)  # оставляем как есть — попадёт в очередь
            mapping = dict(zip(batch, translated))
            cache.put_many(mapping)
            done += len(batch)
            cache.save()
            print(f"  ... переведено {done}/{len(todo)} (кэш {len(cache)})", flush=True)
            if done % 200 < len(batch):
                print(f"  ... переведено {done}/{len(todo)} (кэш {len(cache)})", flush=True)
        cache.save()
        return {ln: cache.get(ln) for ln in lines}

    # -- публичное -------------------------------------------------------
    def translate(self, text: str) -> str:
        """Переводит одну строку целиком (может содержать \\n)."""
        if not text.strip():
            return text
        # 1. строка целиком совпадает с термином глоссария — берём официальное название
        exact = self.protector.lookup_exact(text)
        if exact:
            self.stats["glossary_exact"] += 1
            return exact
        # 2. маскируем структуру и сильные термины глоссария
        masked, tokens = self.protector.protect(text)
        lines = [ln for ln in masked.split("\n") if ln.strip()]
        if not lines:
            return text
        mapping = self._translate_lines(lines)
        rebuilt = []
        for ln in masked.split("\n"):
            if not ln.strip():
                rebuilt.append(ln)
            else:
                rebuilt.append(mapping.get(ln, ln))
        out_masked = "\n".join(rebuilt)
        out = self.protector.restore(out_masked, tokens)
        # DeepL оборачивает незнакомые имена в «ёлочки» — в игре это смотрится чужеродно
        out = out.replace("«", "").replace("»", "")
        # 3. чиним терминологию: DeepL назвал предмет по-своему, в игре он «Хранитель»
        if self.fixer is not None:
            fixed = self.fixer.fix(text, out)
            if fixed != out:
                self.stats["terms_fixed"] += 1
            out = fixed
        self._validate(text, out)
        return out

    def translate_many(self, texts: list[str]) -> list[str]:
        """Переводит много строк, пачками (одно обращение к переводчику на 50 строк)."""
        results: list[str | None] = [None] * len(texts)
        # (индекс, исходник, маскированные строки, токены)
        pending: list[tuple[int, str, list[str], list[str]]] = []

        for i, text in enumerate(texts):
            if not text.strip():
                results[i] = text
                continue
            exact = self.protector.lookup_exact(text)
            if exact:
                self.stats["glossary_exact"] += 1
                results[i] = exact
                continue
            masked, tokens = self.protector.protect(text)
            lines = [ln for ln in masked.split("\n") if ln.strip()]
            if not lines:
                results[i] = text
                continue
            pending.append((i, text, masked.split("\n"), tokens))

        # собираем все уникальные непереведённые строки
        need: list[str] = []
        seen: set[str] = set()
        for _, _, masked_lines, _tok in pending:
            for ln in masked_lines:
                if ln.strip() and ln not in seen and self.cache.get(ln) is None:
                    seen.add(ln)
                    need.append(ln)

        if need:
            self._translate_lines(need)

        for i, text, masked_lines, tokens in pending:
            rebuilt = []
            for ln in masked_lines:
                if not ln.strip():
                    rebuilt.append(ln)
                else:
                    rebuilt.append(self.cache.get(ln, ln))
            out = self.protector.restore("\n".join(rebuilt), tokens)
            out = out.replace("\u00ab", "").replace("\u00bb", "")
            if self.fixer is not None:
                fixed = self.fixer.fix(text, out)
                if fixed != out:
                    self.stats["terms_fixed"] += 1
                out = fixed
            self._validate(text, out)
            results[i] = out
        return [r if r is not None else texts[i] for i, r in enumerate(results)]

    def _validate(self, src: str, out: str) -> None:
        self.stats["total"] += 1
        if not out.strip():
            self.stats["empty"] += 1
            self.manual.append({"src": src, "out": out, "reason": "пустой перевод"})
            return
        # плейсхолдеры
        src_ph = Counter(RE_PLACEHOLDER.findall(src))
        out_ph = Counter(RE_PLACEHOLDER.findall(out))
        if src_ph != out_ph:
            self.stats["placeholder_mismatch"] += 1
            self.manual.append({"src": src, "out": out, "reason": "потеряны плейсхолдеры"})
            return
        # форматирование
        for rx, name in ((RE_TAG, "теги"), (RE_COLOR, "цвета"), (RE_ID, "id")):
            if len(rx.findall(src)) != len(rx.findall(out)):
                self.stats[f"{name}_mismatch"] += 1
                self.manual.append({"src": src, "out": out, "reason": f"потеряны {name}"})
                return
        # невидимые символы
        if len(RE_INVISIBLE.findall(src)) != len(RE_INVISIBLE.findall(out)):
            self.stats["invisible_mismatch"] += 1
            self.manual.append({"src": src, "out": out, "reason": "потерян невидимый символ"})
            return
        # кириллица
        letters = re.findall(r"[A-Za-z]", src)
        has_ru = re.search(r"[Ѐ-ӿ]", out)
        if len(letters) >= 4 and not has_ru and out.strip() == src.strip():
            self.stats["untranslated"] += 1
            self.manual.append({"src": src, "out": out, "reason": "не переведено"})


def load_glossary(path: Path | None = None) -> dict[str, str]:
    p = path or (HERE / "glossary.json")
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def quality(src: str, out: str) -> int:
    """Оценка качества перевода: чем выше, тем лучше.

    Используется, чтобы в ремонтном проходе выбрать лучший из двух вариантов
    (основной перевод и перевод с другим форматом плейсхолдера).
    """
    if not out.strip():
        return -100
    score = 0
    letters = len(re.findall(r"[A-Za-z]", src))
    if letters >= 4:
        score += 2 if re.search(r"[\u0400-\u04ff]", out) else -2
    else:
        score += 1
    # плейсхолдеры обязаны сохраниться
    if Counter(RE_PLACEHOLDER.findall(src)) == Counter(RE_PLACEHOLDER.findall(out)):
        score += 2
    else:
        score -= 8
    # форматирование
    if len(RE_TAG.findall(src)) == len(RE_TAG.findall(out)):
        score += 1
    else:
        score -= 4
    if len(RE_COLOR.findall(src)) == len(RE_COLOR.findall(out)):
        score += 1
    else:
        score -= 3
    if len(RE_ID.findall(src)) == len(RE_ID.findall(out)):
        score += 1
    else:
        score -= 4
    # длина в разумных пределах
    if len(out) > len(src) * 4 or (src and len(out) < len(src) * 0.15):
        score -= 2
    return score
