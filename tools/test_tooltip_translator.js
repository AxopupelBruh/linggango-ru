// Проверка KubeJS-переводчика без игры: эмулируем Forge-объекты.
// Запуск: node test_tooltip_translator.js <путь к .js>
const fs = require('fs');

// ---- эмуляция Component ----
function makeComponent(text, style, siblings) {
  return {
    _text: text,
    _style: style || null,
    _siblings: siblings || [],
    getString() { return this._text + this._siblings.map(s => s.getString()).join(''); },
    getStyle() { return this._style; },
    getSiblings() { return this._siblings; },
  };
}
const Component = {
  literal(text) {
    return {
      _text: text, _style: null, _siblings: [],
      getString() { return this._text; },
      getStyle() { return this._style; },
      getSiblings() { return this._siblings; },
      setStyle(st) { this._style = st; return this; },
    };
  },
};

// ---- эмуляция KubeJS ----
const handlers = [];
const ItemEvents = {
  tooltip(cb) { cb({ addAdvancedToAll(h) { handlers.push(h); } }); },
};
const Java = { loadClass(name) { return Component; } };
const logged = [];
const kconsole = { info: (m) => logged.push(m), error: (m) => logged.push('ERR ' + m) };

// ---- загрузка скрипта ----
const path = process.argv[2];
const src = fs.readFileSync(path, 'utf8');

const fn = new Function('ItemEvents', 'Java', 'console', src);
fn(ItemEvents, Java, kconsole);

// ---- проверки ----
const DICT = JSON.parse(src.match(/var RU_DICT = (\{[\s\S]*?\})\n/)[1]);
const TPL = JSON.parse(src.match(/var RU_TEMPLATES = (\{[\s\S]*?\})\n/)[1]);

function run(lines) {
  const list = {
    _a: lines,
    size() { return this._a.length; },
    get(i) { return this._a[i]; },
    set(i, v) { this._a[i] = v; },
  };
  for (const h of handlers) h(null, false, list);
  return list._a.map(c => c.getString());
}

let ok = 0, fail = 0;
function check(name, got, want) {
  const pass = got === want;
  if (pass) ok++; else fail++;
  console.log(`${pass ? 'OK  ' : 'FAIL'} ${name}\n     got:  ${JSON.stringify(got)}\n     want: ${JSON.stringify(want)}`);
}

// 1. точное совпадение
const k = Object.keys(DICT).find(x => x.includes('§'));
check('§-коды сохраняются', run([makeComponent(k)])[0], DICT[k]);

// 2. без §-кодов
const k2 = Object.keys(DICT).find(x => !x.includes('§') && x.length > 15);
check('обычная строка', run([makeComponent(k2)])[0], DICT[k2]);

// 3. строка не из словаря не меняется
check('чужая строка не тронута', run([makeComponent('Some random english text')])[0], 'Some random english text');

// 4. кириллица не трогается
check('русский не трогается', run([makeComponent('Уже переведено')])[0], 'Уже переведено');

// 5. siblings: переводятся по частям
const sibSrc = Object.keys(DICT).find(x => x.includes('§') && x.length > 20);
const sibPart = sibSrc.split('§')[0] || sibSrc;
const parent = makeComponent('', null, [makeComponent(sibPart)]);
const out = run([parent])[0];
console.log(`${out.includes('§') ? 'OK  ' : 'FAIL'} siblings: ${JSON.stringify(out)}`);

// 6. неизвестная строка попадает в лог
const before = logged.length;
run([makeComponent('Totally unknown english phrase here')]);
console.log(`${logged.length > before ? 'OK  ' : 'FAIL'} неизвестная строка логируется: ${JSON.stringify(logged[logged.length - 1])}`);

// 6b. шаблонное сопоставление (числа/плейсхолдеры)
const withNum = Object.keys(DICT).find(x => /\d/.test(x) && x.length > 12);
if (withNum) {
  const variant = withNum.replace(/\d+/, '42');
  const got = run([makeComponent(variant)])[0];
  const numRe = /\d+/g;
  const want = DICT[withNum].replace(/\d+(?:\.\d+)?/, '42');  // первое число
  check('числа подставляются', got, want);
}

// 7. большой объём: 2000 строк подряд не падает
const many = Object.keys(DICT).slice(0, 2000).map(s => makeComponent(s));
const t0 = Date.now();
const manyOut = run(many);
console.log(`${manyOut.length === 2000 ? 'OK  ' : 'FAIL'} 2000 строк обработано за ${Date.now() - t0} мс`);

console.log(`\nсловарь: ${Object.keys(DICT).length} строк, проверок пройдено: ${ok}, провалено: ${fail}`);
