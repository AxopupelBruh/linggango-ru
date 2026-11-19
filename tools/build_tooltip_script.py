"""Сборка KubeJS-переводчика тултипов.

Скрипт кладётся в kubejs/client_scripts/ru_tooltip_translator.js и переводит
подсказки предметов прямо в игре: KubeJS → Architectury → Forge
ItemTooltipEvent (срабатывает внутри ItemStack#getTooltipLines, поэтому
перевод виден и в инвентаре, и в JEI/REI).

Словарь: work/ui_strings_ru.json (строки из Java-кода модов)
       + work/pack_script_ru.json (строки из скриптов самого пака)

Запуск: python3 build_tooltip_script.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
KUBE = HERE.parent / "kubejs" / "client_scripts"

HEADER = """// ===========================================================================
// Русский перевод подсказок (тултипов) модов — модпак Linggango.
//
// СГЕНЕРИРОВАНО АВТОМАТИЧЕСКИ: .linggango-translate/build_tooltip_script.py
// Правь переводы в work/ui_strings_ru.json и work/pack_script_ru.json,
// потом запусти build_tooltip_script.py заново.
//
// Как это работает:
//   KubeJS -> Architectury -> Forge ItemTooltipEvent.
//   Forge стреляет этим событием прямо внутри ItemStack#getTooltipLines,
//   поэтому перевод работает и в инвентаре, и в JEI/REI, и в подсказках мира.
//
// Неизвестные английские строки пишутся в лог клиента с пометкой [RU-TT] —
// их можно досо��ить офлайн и добавить в словарь.
// ===========================================================================

var Component = null
try {
  Component = Java.loadClass('net.minecraft.network.chat.Component')
} catch (e) {
  Component = null
}

var RU_SEEN = {}

// шаблон строки: числа и плейсхолдеры (%s, %d, %1$s) заменяем меткой,
// чтобы одна и та же фраза подходила при любых значениях
function templateOf(text) {
  return text.replace(/\\d+(?:\\.\\d+)?|%\\d*\\$?[a-zA-Z]|%[a-zA-Z]/g, '\\u0001')
}

function ruOf(text) {
  if (!text) return null
  var r = RU_DICT[text]
  if (r !== undefined && r !== null && r !== '' && r !== text) return r
  // запасной путь: то же предложение, но с другими числами/плейсхолдерами
  var t = templateOf(text)
  var rt = RU_TEMPLATES[t]
  if (rt === undefined || rt === null || rt === '') return null
  return substituteNumbers(text, rt)
}

// переносит значения из показавшейся строки в перевод
function substituteNumbers(src, ru) {
  var nums = src.match(/\\d+(?:\\.\\d+)?/g)
  if (!nums) return ru
  var i = 0
  return ru.replace(/%\\d*\\$?[a-zA-Z]|\\d+(?:\\.\\d+)?/g, function (m) {
    return i < nums.length ? nums[i++] : m
  })
}

function looksEnglish(text) {
  if (!text || text.length < 5) return false
  if (/[\\u0430-\\u044f\\u0451\\u0410-\\u042f\\u0401]/.test(text)) return false
  return /[A-Za-z]{3}/.test(text)
}

function report(text) {
  if (RU_SEEN[text]) return
  RU_SEEN[text] = true
  console.info('[RU-TT] ' + text)
}

// Переводит один компонент. Возвращает новый компонент или null,
// если переводить нечего.
function translateComponent(c) {
  var s = c.getString()
  var ru = ruOf(s)
  if (ru !== null) {
    if (Component === null) return null
    try {
      return Component.literal(ru).setStyle(c.getStyle())
    } catch (e) {
      try {
        return Component.literal(ru)
      } catch (e2) {
        return null
      }
    }
  }

  // строка могла быть собрана из кусочков (siblings)
  var sibs = null
  try {
    sibs = c.getSiblings()
  } catch (e) {
    sibs = null
  }
  var count = 0
  if (sibs !== null) {
    try {
      count = (typeof sibs.size === 'function') ? sibs.size() : sibs.length
    } catch (e) {
      count = 0
    }
  }
  if (count > 0) {
    for (var j = 0; j < count; j++) {
      var sc = sibs.get(j)
      if (sc === null || sc === undefined) continue
      var ss = sc.getString()
      var sru = ruOf(ss)
      if (sru !== null && Component !== null) {
        try {
          sibs.set(j, Component.literal(sru).setStyle(sc.getStyle()))
        } catch (e) {
          /* оставляем как есть */
        }
      } else if (looksEnglish(ss)) {
        report(ss)
      }
    }
  }
  return null
}

ItemEvents.tooltip(function (event) {
  event.addAdvancedToAll(function (item, advanced, lines) {
    try {
      for (var i = 0; i < lines.size(); i++) {
        var c = lines.get(i)
        var nu = translateComponent(c)
        if (nu !== null) {
          lines.set(i, nu)
        } else {
          var s = c.getString()
          if (looksEnglish(s)) report(s)
        }
      }
    } catch (e) {
      console.error('[RU-TT] ошибка при переводе: ' + e)
    }
  })
})
"""


def load_dict() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("ui_strings_ru.json", "pack_script_ru.json", "runtime_missing_ru.json",
                 "ui_strings_manual_ru.json"):
        p = WORK / name
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for k, v in data.items():
            if not k or not v or k == v:
                continue
            out[k] = v
    return out


def template_of(text: str) -> str:
    """Шаблон строки: числа и плейсхолдеры заменяются меткой."""
    return re.sub(r"\d+(?:\.\d+)?|%\d*\$?[a-zA-Z]|%[a-zA-Z]", "\u0001", text)


def main() -> int:
    d = load_dict()
    templates: dict[str, str] = {}
    for k, v in d.items():
        t = template_of(k)
        if t not in templates:
            templates[t] = v
    body = ("var RU_DICT = " + json.dumps(d, ensure_ascii=False, indent=0) + "\n\n"
            "var RU_TEMPLATES = " + json.dumps(templates, ensure_ascii=False, indent=0) + "\n")
    text = HEADER + "\n" + body
    out = KUBE / "ru_tooltip_translator.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    mirror = HERE / "generated_ru_tooltip_translator.js"
    mirror.write_text(text, encoding="utf-8")
    print(f"словарь: {len(d)} строк, шаблонов: {len(templates)}")
    print(f"записан: {out}  ({out.stat().st_size} байт)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
