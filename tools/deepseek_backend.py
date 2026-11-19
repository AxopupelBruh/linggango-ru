"""Бэкенд перевода через DeepSeek V4.1 Flash (OpenAI-совместимый API).

Провайдер: https://100milionseek.top/v1 , модель deepseek-v4.1-flash-free
(100 млн токенов в сутки бесплатно).

Интерфейс совпадает с GoogleBackend/DeepLBackend/GeminiBackend из tr_engine:
    translate_batch(lines: list[str]) -> list[str]
Возвращает столько же строк, сколько было на входе.

Ключ берётся из HMS_API_KEY / DEEPSEEK_API_KEY или из файла .deepseek_key рядом со скриптом.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

SYSTEM_RULES = """Ты — профессиональный переводчик игровых локализаций. Ты переводишь английские
строки интерфейса, предметов, зачарований, способностей, заданий и подсказок Minecraft-модпака
на русский язык. Твой перевод попадёт в игру к игрокам, поэтому он должен звучать как
нативный русский игровой текст, а не как машинный перевод.

═══════════════════════════════════════════
1. ЯЗЫК И СТИЛЬ
═══════════════════════════════════════════
• Переводи на современный литературный русский. Стиль — живой игровой: коротко, понятно,
  без канцелярита и без «переводчика» на лбу.
• Пиши так, как это сказал бы русскоязычный игрок или модератор. Никаких калек
  («увеличивает Вашу Силу» → «повышает силу», «при нацеливании на цель» → «попадая в цель»).
• Не добавляй и не выбрасывай смысл. Не сокращай текст, не добавляй пояснений, комментариев,
  кавычек или знаков препинания, которых не было.
• Не переводи слова, которые игроки видят как идентификаторы: названия модов и брендов
  (FTB, JEI, REI, WTHIT, Create, Mekanism, Ars Nouveau, Curios, Jade, Xaero's,
  Immersive Engineering, Sophisticated Storage, Occultism, Ad Astra, Botania, Patchouli
  и любые другие названия модов), имена игроков, ники, имена файлов, идентификаторы предметов.
• Единицы измерения оставляй как в оригинале (HP, XP, mB, dmg, t), числа — без изменений.

═══════════════════════════════════════════
2. ГРАММАТИКА РУССКОГО ЯЗЫКА
═══════════════════════════════════════════
• Согласуй всё: падеж, число, род. «Увеличивает Вашу Максимальную Здоровье» — неверно,
  правильно «повышает максимальное здоровье».
• Не оставляй в русском тексте английские окончания: «Уроном от Кровотечения», а не
  «Кровотечением уроном». Если в оригинале падеж не задаётся грамматикой, выбери тот,
  который требует русский язык в этом предложении.
• Универсальные игровые термины: Зачарования, Снаряжение, Эффект, Урон, Здоровье, Опыт,
  Уровень, Ресурс, Блок, Предмет, Инструмент, Броня, Ферма, Печь, Энергия, Жидкость,
  Флюид, Сеть, Автоматизация, Сканирование, Руда, Слиток, Порошок, Кристалл.
• Не переводи насильно обычные глаголы и бытовые слова: «place» → «установить»/«поставить»,
  «hold» → «удерживайте», «open» → «открыть», «insert» → «вставьте», «consume» → «используйте».
• Обращения к игроку — в повелительном наклонении или в принятой игровой форме
  («Нажмите», «Используйте», «Вставьте»), без «Вы» с большой буквы, если в оригинале его нет.

═══════════════════════════════════════════
3. НАЗВАНИЯ СПОСОБНОСТЕЙ, ЗАЧАРОВАНИЙ, ЭФФЕКТОВ
═══════════════════════════════════════════
• Это игровые фэнтезийные имена. Переводи их принятым русским игровым вариантом,
  а НЕ буквальной калькой.
  ✗ Blood Drain → «Кровь Водосток»      ✓ Blood Drain → «Кровопускание»
  ✗ Cosmic Sickness → «Космическая болезнь (заразна)» ✓ Cosmic Sickness → «Космическая болезнь»
  ✗ Verdoyance → «Зеленение»            ✓ Verdoyance → «Зеленение» / «Заросли» (по смыслу)
  ✗ Divine Retribution → «Божественная Возмездия» ✓ Divine Retribution → «Божественное возмездие»
  ✗ Headbreaker → «Головолом»           ✓ Headbreaker → «Дробящий череп» / «Раскалыватель черепа»
• Способности-эффекты, которые накладываются на цель, согласуй с «эффект»:
  «накладывает эффект Кровотечения», «эффект Божественного возмездия накапливается».
• Если название — общеизвестное русское слово (Кровь, Скорость, Защита, Ярость), оставь
  его как есть.

═══════════════════════════════════════════
4. ФОРМАТИРОВАНИЕ MINECRAFT (НЕ ТРОГАТЬ)
═══════════════════════════════════════════
• §- и &-коды цвета (§a, §7, &c, §x), hex-цвета (#RRGGBB), теги (<typewriter>, <grad ...>,
  <shadow ...>, <click ...>), плейсхолдеры (%s, %d, %1$s, %.2f, {0}, {}), идентификаторы
  (minecraft:stone, entity.player), команды (/give), URL и имена файлов — переносятся
  в перевод БЕЗ ИЗМЕНЕНИЙ, посимвольно. Даже если они стоят внутри фразы.
• Токены вида [[0]], [[1]] — это защищённые фрагменты. Верни их на свои места без изменений,
  ничего не переставляй и не выбрасывай.
• Зачарование в квадратных скобках (§4[Blood Drain]) переводится ВНУТРИ скобок,
  сами скобки и коды цвета остаются на месте.
• Сохраняй количество пробелов и отступов в начале/конце строки.
• Если строка состоит только из символов, чисел, кодов или форматирования — верни её
  без изменений, ничего не придумывая.

═══════════════════════════════════════════
5. РЕГИСТР
═══════════════════════════════════════════
• Title Case в оригинале → Title Case в переводе: «Cosmic Sickness» → «Космическая болезнь».
• Обычное предложение с маленькой буквы → с маленькой буквы: «the basic sweetspot» →
  «базовая зона попадания».
• Имена предметов, боссов, способностей и зачарований с большой буквы → с большой буквы.
• Всё, что стоит в начале строки после §-кода цвета, — тоже первая буква предложения.

═══════════════════════════════════════════
6. ПОДСКАЗКИ ПО ТЕРМИНАМ (поле terms)
═══════════════════════════════════════════
• У каждой входной строки есть поле terms — словарь принятых в этом модпаке переводов.
  Если термин из terms встречается в строке, используй именно этот русский вариант.
• Но СКЛОНЯЙ термин по-русски как того требует предложение:
  terms: {"Divine Retribution": "Божественное возмездие"}
  строка: "Allow the Divine Retribution effect to build up faster"
  ответ: "Позволяет эффекту Божественного возмездия накапливаться быстрее"
• Если термин из terms — название мода или бренда, оставь его латиницей.

═══════════════════════════════════════════
7. ФОРМАТ ОТВЕТА
═══════════════════════════════════════════
• Верни ТОЛЬКО JSON-объект вида {"translations": ["перевод1", "перевод2", ...]}.
• Количество переводов равно количеству входных строк, порядок — 1:1.
• Никакого текста вокруг JSON, никаких комментариев, никаких ```-ограждений.
• Каждый перевод — строка JSON. Ничего не форматируй переносами строк внутри строки.

═══════════════════════════════════════════
ПРИМЕРЫ
═══════════════════════════════════════════
EN: " §7Adds +1 §bCosmic Sickness §7effect to the target with any §bCosmic §7weapon"
RU: " §7Добавляет +1 §bКосмическую болезнь §7к цели при попадании любым §bкосмическим §7оружием"

EN: " §4[Blood Drain]"
RU: " §4[Кровопускание]"

EN: "The basic sweetspot."
RU: "Базовая зона попадания."

EN: "Interact with the block to open the %s interface."
RU: "Взаимодействуйте с блоком, чтобы открыть интерфейс %s."

EN: "  §9+1 Armor "
RU: "  §9+1 к броне "

EN: "Creature"
RU: "Существо"
"""

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.M)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class DeepSeekBackend:
    name = "deepseek"
    URL = "https://100milionseek.top/v1/chat/completions"
    max_items = 80
    max_chars = 20000

    def __init__(self, api_key: str | None = None, model: str = "deepseek-v4.1-flash-free",
                 base_url: str | None = None, delay: float = 0.4, temperature: float = 0.1,
                 thinking: bool = False):
        key = (api_key or os.environ.get("HMS_API_KEY")
               or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not key:
            key_file = HERE / ".deepseek_key"
            if key_file.exists():
                key = key_file.read_text(encoding="utf-8").strip()
        if not key:
            raise RuntimeError("deepseek: нет ключа (HMS_API_KEY или .deepseek_key)")
        self.api_key = key
        self.model = model
        self.base_url = (base_url or os.environ.get("HMS_BASE_URL")
                         or "https://100milionseek.top/v1").rstrip("/")
        self.delay = delay
        self.temperature = temperature
        self.thinking = thinking
        self._lock = threading.Lock()
        self._last = 0.0
        self.calls = 0
        self.input_chars = 0
        self.output_chars = 0

        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        })

    def _throttle(self) -> None:
        with self._lock:
            gap = time.time() - self._last
            if gap < self.delay:
                time.sleep(self.delay - gap)
            self._last = time.time()

    def _prompt(self, lines: list[str]) -> str:
        payload = json.dumps(lines, ensure_ascii=False)
        return (
            "Переведи английские строки на русский по правилам из системного сообщения.\n"
            f"Строк: {len(lines)}. Верни JSON-объект {{\"translations\": [...]}}.\n"
            f"Исходные строки:\n{payload}"
        )

    def _parse(self, text: str, n: int) -> list[str]:
        raw = _FENCE.sub("", text or "").strip()
        data = None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("["), raw.rfind("]")
            if start >= 0 and end > start:
                try:
                    data = json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    data = None
            if data is None:
                # мог прийти объект-обёртка
                ob = raw.find("{")
                cb = raw.rfind("}")
                if ob >= 0 and cb > ob:
                    try:
                        obj = json.loads(raw[ob:cb + 1])
                        for v in obj.values():
                            if isinstance(v, list) and len(v) == n:
                                data = v
                                break
                    except json.JSONDecodeError:
                        data = None
        if not isinstance(data, list) or len(data) != n:
            got = len(data) if isinstance(data, list) else "не список"
            raise RuntimeError(f"deepseek: ожидалось {n} строк, получено {got}")
        return [str(x) for x in data]

    def _request(self, lines: list[str]) -> list[str]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_RULES},
                {"role": "user", "content": self._prompt(lines)},
            ],
            "temperature": self.temperature,
            "max_tokens": 8192,
            "stream": False,
        }
        if not self.thinking:
            body["thinking"] = {"type": "disabled"}
        last = ""
        for attempt in range(6):
            try:
                self._throttle()
                r = self.session.post(self.base_url + "/chat/completions", json=body, timeout=300)
                self.calls += 1
                if r.status_code == 200:
                    data = r.json()
                    msg = data["choices"][0]["message"]
                    text = msg.get("content") or ""
                    if not text:
                        # модель ушла в tool_calls — повторяем с явным запретом
                        raise RuntimeError("deepseek: пустой content")
                    self.input_chars += len(self._prompt(lines))
                    self.output_chars += len(text)
                    return self._parse(text, len(lines))
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 403, 404):
                    raise RuntimeError(f"deepseek: {last}")
                if r.status_code in (429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                    time.sleep(min(60, 8 * (attempt + 1)) + random.uniform(0, 3))
                    continue
                raise RuntimeError(f"deepseek: {last}")
            except RuntimeError as exc:
                last = str(exc)
                if attempt == 5:
                    raise
                time.sleep(5 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
                if attempt == 5:
                    raise RuntimeError(f"deepseek: {last}") from exc
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"deepseek: {last}")

    def translate_batch(self, lines: list[str]) -> list[str]:
        if not lines:
            return []
        if len(lines) <= self.max_items and sum(len(x) for x in lines) <= self.max_chars:
            return self._request(lines)
        out: list[str] = []
        chunk: list[str] = []
        size = 0
        for ln in lines:
            if chunk and (len(chunk) >= self.max_items or size + len(ln) > self.max_chars):
                out.extend(self._request(chunk))
                chunk, size = [], 0
            chunk.append(ln)
            size += len(ln)
        if chunk:
            out.extend(self._request(chunk))
        return out

    # ------------------------------------------------------------------
    # Перевод с подсказками терминов
    # ------------------------------------------------------------------

    def _prompt_hinted(self, items: list[dict]) -> str:
        payload = json.dumps(items, ensure_ascii=False)
        return (
            "Входные строки (en — английский текст с защищёнными токенами [[N]], "
            "terms — принятые переводы терминов):\n" + payload
        )

    def _request_hinted(self, items: list[dict]) -> list[str]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_RULES},
                {"role": "user", "content": self._prompt_hinted(items)},
            ],
            "temperature": self.temperature,
            "max_tokens": 8192,
            "stream": False,
        }
        last = ""
        for attempt in range(6):
            try:
                self._throttle()
                r = self.session.post(self.base_url + "/chat/completions", json=body, timeout=300)
                self.calls += 1
                if r.status_code == 200:
                    data = r.json()
                    msg = data["choices"][0]["message"]
                    text = msg.get("content") or ""
                    if not text:
                        raise RuntimeError("deepseek: пустой content")
                    self.input_chars += len(self._prompt_hinted(items))
                    self.output_chars += len(text)
                    return self._parse_obj(text, len(items))
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 403, 404):
                    raise RuntimeError(f"deepseek: {last}")
                if r.status_code in (429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                    time.sleep(min(60, 8 * (attempt + 1)) + random.uniform(0, 3))
                    continue
                raise RuntimeError(f"deepseek: {last}")
            except RuntimeError as exc:
                last = str(exc)
                if attempt == 5:
                    raise
                time.sleep(5 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
                if attempt == 5:
                    raise RuntimeError(f"deepseek: {last}") from exc
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"deepseek: {last}")

    def _parse_obj(self, text: str, n: int) -> list[str]:
        raw = _FENCE.sub("", text or "").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            ob, cb = raw.find("{"), raw.rfind("}")
            if ob < 0 or cb <= ob:
                raise RuntimeError(f"deepseek: не разобрал JSON: {raw[:200]}")
            data = json.loads(raw[ob:cb + 1])
        if isinstance(data, dict):
            for key in ("translations", "result", "results", "ru", "items"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list) or len(data) != n:
            got = len(data) if isinstance(data, list) else "не список"
            raise RuntimeError(f"deepseek: ожидалось {n} строк, получено {got}")
        return [str(x) for x in data]

    def translate_batch_hinted(self, items: list[dict]) -> list[str]:
        """items: [{"en": str, "terms": {EN: RU}}, ...] -> список переводов."""
        if not items:
            return []
        out: list[str] = []
        chunk: list[dict] = []
        size = 0
        for it in items:
            ln = it["en"]
            if chunk and (len(chunk) >= self.max_items or size + len(ln) > self.max_chars):
                out.extend(self._request_hinted(chunk))
                chunk, size = [], 0
            chunk.append(it)
            size += len(ln)
        if chunk:
            out.extend(self._request_hinted(chunk))
        return out
