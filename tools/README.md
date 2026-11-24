# Инструменты перевода

Скрипты, которыми сделан перевод Linggango. Это рабочий конвейер, а не
разовые правки: каждый шаг можно повторить на текущей версии сборки.

## Как запускать

Скрипты ждут инстанс сборки. Путь берётся из трёх источников по порядку:

1. переменная окружения `LINGGANGO_INSTANCE`;
2. файл `instance.path` рядом со скриптами (одна строка с путём);
3. значение по умолчанию из `paths.py`.

```bash
export LINGGANGO_INSTANCE="/путь/к/папке/сборки"
python3 paths.py     # покажет, куда смотрит скрипт
```

## Конвейер

```bash
# 1. разведка: что вообще есть в сборке
python3 collect.py                       # строки из Java-кода модов
python3 collect_extra.py                 # строки из конфигов и скриптов пака
python3 fill_lang_gap.py                 # чего не хватает в словарях

# 2. перевод (нужен ключ DeepSeek в .deepseek_key или DeepL в .deepl_key)
python3 run.py --source mods --out mods_ru
python3 translate_ui_deepseek.py         # интерфейсные строки
python3 translate_runtime_missing.py     # строки из лога игры

# 3. чистка перевода
python3 lint_calc.py work/mods_ru.json --fix   # кальки без модели
python3 polish_ru.py                          # обрывы текста, «ты/вы»
python3 repair_markup.py                      # §-коды, плейсхолдеры
python3 fix_zwnj.py                           # неразрывные пробелы

# 4. сборка
python3 build_resourcepack.py                # → resourcepacks/zz_linggango_ru.zip
python3 fix_books.py build                   # → датапак с книгами в данжах
python3 build_tooltip_script.py              # → kubejs/client_scripts/ru_tooltip_translator.js

# 5. проверка
python3 verify_all.py                        # → «ВСЁ ОК»
python3 verify_pack.py                       # полнота lang-файлов пака
python3 audit_font_coverage.py               # символы без глифа в шрифте игры
python3 audit_terms.py                       # разнобой терминов

# 6. публикация
python3 publish_release.py --push            # собрать и залить репозиторий
python3 build_release_archive.py             # → release/linggango-ru-v6.6.6.zip
```

## Как устроен сборщик ресурспака

Главное правило, из-за которого всё ломается чаще всего:

> **lang-файл ресурспака ЗАМЕНЯЕТ файл мода целиком, а не дополняет его.**

Поэтому `build_resourcepack.py` пишет в каждый неймспейс **объединение всех
источников**, которые видны в игре:

1. `assets/<ns>/lang/ru_ru.json` из jar-ов модов;
2. пак KubeJS — `kubejs/assets/<ns>/lang/ru_ru.json`;
3. пак serilum — `data/serilum/translations/assets/<ns>/lang/ru_ru.json`;
4. чужие локализации — `MPLOCmods.zip` (только для модов, что есть в сборке);
5. наши переводы — поверх.

Снимок пункта 4 лежит в `data/mploc_ru.json`: сборка повторится, даже если
пака-источника не окажется на диске. Сам `MPLOCmods` в игре больше не нужен.

Модуль `lang_sources.py` отвечает за сбор источников, `build_resourcepack.py` —
за то, как из них получается финальный файл.

## Что важно не сломать

- **§-коды, плейсхолдеры (`%s`, `%d`, `$(item)`), теги и id** маскируются
  токенами до перевода и возвращаются на место после. Никогда не отдавай их
  переводчику.
- **Ванильный `ru_ru`** (8 799 ключей) встроен в пак. Если приложить свой
  `assets/minecraft/lang/ru_ru.json` с парой ключей — весь интерфейс игры
  уйдёт на английский.
- **Шрифт** `assets/minecraft/font/default.json` в стеке ресурспаков один на
  всех: побеждает тот, что выше в списке. Сборщик собирает в него
  bitmap-провайдеры всех модов — иначе иконки brutality, simplyswords и bbb
  превращаются в квадраты.
- **Квесты зашифрованы** ключом из констант мода `linggango_tweaks` (формат
  `LGQ1:`). Правка — через `lgq_crypt.py`, шифрование сохраняется.
- **Jar-файлы модов не патчатся.** Весь перевод — во внешних слоях: ресурспак,
  датапак, скрипты. Иначе перевод пропадёт при обновлении сборки.

## Ключи API

Лежат в `tools/.deepl_key*`, `.deepseek_key*`, `.gemini_key`. В репозиторий
не попадают — сборщик релиза вырезает их и проверяет результат.
