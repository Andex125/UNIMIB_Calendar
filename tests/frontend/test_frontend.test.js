const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appJsPath = fs.existsSync(path.join(__dirname, '../../public/js/app.js'))
  ? path.join(__dirname, '../../public/js/app.js')
  : path.join(__dirname, '../public/js/app.js');
const appJsCode = fs.readFileSync(appJsPath, 'utf8');

// Full mock environment for app.js
const mockElement = () => ({
  addEventListener: () => {},
  removeEventListener: () => {},
  setAttribute: () => {},
  removeAttribute: () => {},
  getAttribute: () => null,
  classList: {
    add: () => {},
    remove: () => {},
    toggle: () => {},
    contains: () => false
  },
  style: {},
  children: [],
  childNodes: [],
  appendChild: () => {},
  removeChild: () => {},
  innerHTML: '',
  textContent: '',
  value: ''
});

const sandbox = {
  window: {},
  document: {
    addEventListener: () => {},
    removeEventListener: () => {},
    getElementById: () => mockElement(),
    querySelector: () => mockElement(),
    querySelectorAll: () => [],
    createElement: () => mockElement(),
    documentElement: mockElement(),
    body: mockElement()
  },
  navigator: { onLine: true, serviceWorker: { register: () => Promise.resolve() } },
  localStorage: {
    _data: {},
    getItem(k) { return this._data[k] ?? null; },
    setItem(k, v) { this._data[k] = String(v); },
    removeItem(k) { delete this._data[k]; },
    clear() { this._data = {}; }
  },
  sessionStorage: {
    _data: {},
    getItem(k) { return this._data[k] ?? null; },
    setItem(k, v) { this._data[k] = String(v); },
    removeItem(k) { delete this._data[k]; }
  },
  location: { search: '', href: 'http://localhost/', pathname: '/' },
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Date,
  Math,
  RegExp,
  JSON,
  parseInt,
  parseFloat,
  encodeURIComponent,
  decodeURIComponent
};
sandbox.window = sandbox;

const context = vm.createContext(sandbox);
vm.runInContext(appJsCode, context);

test('detectAreaColor maps degrees and keywords to correct colors', () => {
  const detectAreaColor = sandbox.detectAreaColor;
  assert.ok(typeof detectAreaColor === 'function');
  
  // Informatica -> scientifica (#00753B)
  assert.strictEqual(detectAreaColor('Informatica'), '#00753B');
  // Medicina -> medica (#D83424)
  assert.strictEqual(detectAreaColor('Medicina e Chirurgia'), '#D83424');
  // Economia -> economica (#E5C200)
  assert.strictEqual(detectAreaColor('Economia Aziendale'), '#E5C200');
  // Giurisprudenza -> giuridica (#005096)
  assert.strictEqual(detectAreaColor('Giurisprudenza'), '#005096');
  // Unknown -> null
  assert.strictEqual(detectAreaColor('Corso Sconosciuto'), null);
  assert.strictEqual(detectAreaColor(null), null);
});

test('extractBuildingCode and getBuildingMapUrl handle UNIMIB buildings U1-U28', () => {
  const extractBuildingCode = sandbox.extractBuildingCode;
  const getBuildingMapUrl = sandbox.getBuildingMapUrl;

  assert.strictEqual(extractBuildingCode('Aula U1-01'), 'U1');
  assert.strictEqual(extractBuildingCode('U07 Laboratorio'), 'U7');
  assert.strictEqual(extractBuildingCode('Aula U24/02'), 'U24');
  assert.strictEqual(extractBuildingCode('Edificio U14'), 'U14');
  assert.strictEqual(extractBuildingCode('Nessuna aula'), null);

  const mapU1 = getBuildingMapUrl('U1');
  assert.ok(mapU1.includes('google.com/maps'));
  assert.ok(mapU1.includes('Piazza%20della%20Scienza'));

  const mapU7 = getBuildingMapUrl('U7');
  assert.ok(mapU7.includes('google.com/maps'));
});

test('escapeHtml prevents XSS injection', () => {
  const escapeHtml = sandbox.escapeHtml;
  assert.strictEqual(escapeHtml('<script>alert("xss")</script>'), '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  assert.strictEqual(escapeHtml("Tom & Jerry's"), 'Tom &amp; Jerry&#39;s');
  assert.strictEqual(escapeHtml(''), '');
  assert.strictEqual(escapeHtml(null), '');
});

test('Date utilities: getMonday, formatFormattedDate, formatDateIso, parseAnyDate', () => {
  const getMonday = sandbox.getMonday;
  const formatFormattedDate = sandbox.formatFormattedDate;
  const formatDateIso = sandbox.formatDateIso;
  const parseAnyDate = sandbox.parseAnyDate;
  const dateFormattedToIso = sandbox.dateFormattedToIso;

  // 2026-10-07 is Wednesday
  const wed = new Date(2026, 9, 7);
  const mon = getMonday(wed);
  assert.strictEqual(mon.getDay(), 1); // Monday
  assert.strictEqual(formatFormattedDate(mon), '05-10-2026');
  assert.strictEqual(formatDateIso(mon), '2026-10-05');

  // parseAnyDate
  const parsed1 = parseAnyDate('05-10-2026');
  assert.strictEqual(parsed1.getDate(), 5);
  assert.strictEqual(parsed1.getMonth(), 9);
  assert.strictEqual(parsed1.getFullYear(), 2026);

  const parsed2 = parseAnyDate('2026-10-05');
  assert.strictEqual(parsed2.getDate(), 5);

  // dateFormattedToIso
  assert.strictEqual(dateFormattedToIso('05-10-2026'), '2026-10-05');
});

test('formatDateItalianLong and formatDateItalianShort produce valid Italian dates', () => {
  const formatDateItalianLong = sandbox.formatDateItalianLong;
  const formatDateItalianShort = sandbox.formatDateItalianShort;

  const d = new Date(2026, 9, 5); // 5 Ottobre 2026 (Lunedì)
  const longStr = formatDateItalianLong(d);
  assert.ok(longStr.toLowerCase().includes('lunedì'));
  assert.ok(longStr.toLowerCase().includes('ottobre'));
  assert.ok(longStr.includes('2026'));

  const shortStr = formatDateItalianShort(d);
  assert.strictEqual(shortStr, '05/10/2026');
});

test('hexToRgba converts hex colors to rgba string without spaces', () => {
  const hexToRgba = sandbox.hexToRgba;
  assert.strictEqual(hexToRgba('#3B82F6', 0.5), 'rgba(59,130,246,0.5)');
  assert.strictEqual(hexToRgba('#000000', 1), 'rgba(0,0,0,1)');
});

test('addHoursToTime handles hour calculations correctly', () => {
  const addHoursToTime = sandbox.addHoursToTime;
  assert.strictEqual(addHoursToTime('08:30', 2), '10:30');
  assert.strictEqual(addHoursToTime('22:00', 1), '23:00');
  assert.strictEqual(addHoursToTime('23:00', 1), '23:00'); // capped at 23
});

test('normalizeSearchText cleans diacritics and trims text', () => {
  const normalizeSearchText = sandbox.normalizeSearchText;
  assert.strictEqual(normalizeSearchText('Lunedì'), 'lunedi');
  assert.strictEqual(normalizeSearchText('   ANALISI   '), 'analisi');
  assert.strictEqual(normalizeSearchText(''), '');
});

test('generateChangesHash creates deterministic signatures', () => {
  const generateChangesHash = sandbox.generateChangesHash;
  const changesA = [
    { type: 'modified', event: { id: 'ev1', course: 'Analisi 1' } },
    { type: 'cancelled', event: { id: 'ev2', course: 'Fisica' } }
  ];
  const changesB = [
    { type: 'modified', event: { id: 'ev1', course: 'Analisi 1' } },
    { type: 'cancelled', event: { id: 'ev2', course: 'Fisica' } }
  ];
  assert.strictEqual(generateChangesHash(changesA), generateChangesHash(changesB));
});

test('getExamDateRange returns valid date ranges for sessions', () => {
  const getExamDateRange = sandbox.getExamDateRange;
  const winter = getExamDateRange('winter');
  assert.ok(winter.from);
  assert.ok(winter.to);

  const summer = getExamDateRange('summer');
  assert.ok(summer.from);
  assert.ok(summer.to);

  const autumn = getExamDateRange('autumn');
  assert.ok(autumn.from);
  assert.ok(autumn.to);
});

test('isFavorite checks whether an event matches marked favorite colors', () => {
  const isFavorite = sandbox.isFavorite;
  const appState = vm.runInContext('state', context);
  appState.favoriteColors = {
    'INF101': '#DC2626'
  };
  assert.strictEqual(isFavorite({ course_code: 'INF101' }), true);
  assert.strictEqual(isFavorite({ course_code: 'INF999' }), false);
  assert.strictEqual(isFavorite({}), false);
});

test('choiceItemHtml generates accessible markup for checkboxes', () => {
  const choiceItemHtml = sandbox.choiceItemHtml;
  const html = choiceItemHtml('val1', 'Label 1', 'Hint text', true);
  assert.ok(html.includes('value="val1"'));
  assert.ok(html.includes('checked'));
  assert.ok(html.includes('Label 1'));
  assert.ok(html.includes('Hint text'));
});

test('safeHtmlTag template literal sanitizes dynamic variables against XSS', () => {
  const safeHtmlTag = sandbox.safeHtmlTag;
  assert.ok(typeof safeHtmlTag === 'function');
  const userContent = '<script>alert("xss")</script>';
  const res = safeHtmlTag`<div class="test">${userContent}</div>`;
  assert.strictEqual(res, '<div class="test">&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</div>');

  // Supports pre-sanitized __isSafeHtml objects
  const safeObj = { __isSafeHtml: true, content: '<span>Safe</span>' };
  const res2 = safeHtmlTag`<div>${safeObj}</div>`;
  assert.strictEqual(res2, '<div><span>Safe</span></div>');
});

test('announceA11y updates live region element text content asynchronously', (t, done) => {
  const announceA11y = sandbox.announceA11y;
  assert.ok(typeof announceA11y === 'function');

  let announcerEl = { textContent: '' };
  sandbox.document.getElementById = (id) => {
    if (id === 'a11yAnnouncer') return announcerEl;
    return mockElement();
  };

  announceA11y('Filtri aggiornati con successo');
  setTimeout(() => {
    assert.strictEqual(announcerEl.textContent, 'Filtri aggiornati con successo');
    done();
  }, 100);
});

