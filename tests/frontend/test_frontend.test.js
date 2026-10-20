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
const mockElement = () => {
  const _listeners = {};
  return {
    _listeners,
    addEventListener: (ev, fn) => {
      if (!_listeners[ev]) _listeners[ev] = [];
      _listeners[ev].push(fn);
    },
    removeEventListener: (ev, fn) => {
      if (_listeners[ev]) _listeners[ev] = _listeners[ev].filter(f => f !== fn);
    },
    click: function() {
      (_listeners['click'] || []).forEach(fn => fn({ preventDefault: () => {}, stopPropagation: () => {} }));
    },
    setAttribute: () => {},
    removeAttribute: () => {},
    getAttribute: () => null,
    scrollIntoView: () => {},
    classList: {
      add: () => {},
      remove: () => {},
      toggle: () => {},
      contains: () => false
    },
    style: {
      setProperty: () => {},
      removeProperty: () => {},
      getPropertyValue: () => ''
    },
    children: [],
    childNodes: [],
    appendChild: function(c) {
      if (!this.children) this.children = [];
      if (!this.childNodes) this.childNodes = [];
      this.children.push(c);
      this.childNodes.push(c);
      return c;
    },
    removeChild: function(c) {
      if (this.children) this.children = this.children.filter(x => x !== c);
      if (this.childNodes) this.childNodes = this.childNodes.filter(x => x !== c);
      return c;
    },
    querySelector: () => mockElement(),
    querySelectorAll: () => [],
    innerHTML: '',
    textContent: '',
    value: ''
  };
};

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
  requestAnimationFrame: (cb) => setTimeout(cb, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
  Date,
  Math,
  RegExp,
  JSON,
  parseInt,
  parseFloat,
  encodeURIComponent,
  decodeURIComponent,
  URLSearchParams,
  URL,
  Blob: typeof Blob !== 'undefined' ? Blob : function() {},
  Option: function(text, val) { return { text: text || '', value: val !== undefined ? val : (text || '') }; }
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

test('highlightMatch safely highlights queries without corrupting HTML entities', () => {
  const highlightMatch = sandbox.highlightMatch;
  assert.ok(typeof highlightMatch === 'function');

  // Matches query and wraps in <mark>
  const res1 = highlightMatch('Programmazione 1', 'programma');
  assert.strictEqual(res1, '<mark class="search-highlight">Programma</mark>zione 1');

  // Safe against ampersands without creating broken entities
  const res2 = highlightMatch('Economia & Finanza', '&');
  assert.strictEqual(res2, 'Economia <mark class="search-highlight">&amp;</mark> Finanza');

  // Regex special characters in query are escaped
  const res3 = highlightMatch('Fisica (Canale A)', '(Canale A)');
  assert.strictEqual(res3, 'Fisica <mark class="search-highlight">(Canale A)</mark>');

  // Null or empty handling
  assert.strictEqual(highlightMatch('', 'query'), '');
  assert.strictEqual(highlightMatch('Test', ''), 'Test');
});

test('renderBuildingBadgeHtml generates valid campus map badge markup', () => {
  const renderBuildingBadgeHtml = sandbox.renderBuildingBadgeHtml;
  assert.ok(typeof renderBuildingBadgeHtml === 'function');

  // Valid building code
  const htmlU1 = renderBuildingBadgeHtml('Aula U1-02');
  assert.ok(htmlU1.includes('building-badge'));
  assert.ok(htmlU1.includes('U1'));
  assert.ok(htmlU1.includes('google.com/maps'));

  // Building without code returns empty string
  const empty = renderBuildingBadgeHtml('Aula Magna Esterna');
  assert.strictEqual(empty, '');
});

test('debounce delays function execution until wait interval expires', (t, done) => {
  const debounce = sandbox.debounce;
  assert.ok(typeof debounce === 'function');

  let callCount = 0;
  const debouncedFn = debounce(() => {
    callCount++;
  }, 50);

  debouncedFn();
  debouncedFn();
  debouncedFn();
  assert.strictEqual(callCount, 0);

  setTimeout(() => {
    assert.strictEqual(callCount, 1);
    done();
  }, 80);
});

test('safeLoadConfig retrieves valid config and recovers from corrupt storage safely', () => {
  const safeLoadConfig = sandbox.safeLoadConfig;
  const configKey = 'unimib_config';

  // 1. Valid config
  const validCfg = {
    anno: '2026',
    corso: 'F1801Q',
    anni: ['1'],
    favorites: [{ code: 'INF101' }]
  };
  sandbox.localStorage.setItem(configKey, JSON.stringify(validCfg));
  const loaded = safeLoadConfig();
  assert.strictEqual(loaded.corso, 'F1801Q');
  assert.strictEqual(loaded.favorites.length, 1);

  // 2. Corrupt JSON in localStorage
  sandbox.localStorage.setItem(configKey, '{corrupted-json:');
  const fallback = safeLoadConfig();
  assert.strictEqual(fallback, null);
  // Backup was created
  assert.ok(sandbox.localStorage.getItem('unimib_config_backup'));
});

test('days-tab-bar has margin-top: 2px and addExternalCourseModal has elevated z-index in CSS', () => {
  const cssPath = path.join(__dirname, '../../public/css/style.css');
  const css = fs.readFileSync(cssPath, 'utf8');

  // Verify .days-tab-bar has margin-top: 2px
  assert.match(css, /\.days-tab-bar\s*\{[^}]*margin-top:\s*2px/s, 'Expected .days-tab-bar to have margin-top: 2px');

  // Verify #addExternalCourseModal has z-index: 1100
  assert.match(css, /#addExternalCourseModal\s*\{[^}]*z-index:\s*1100/s, 'Expected #addExternalCourseModal to have z-index: 1100');
});

test('HTML modal hierarchy places addExternalCourseModal after setupModal and includes multi-select', () => {
  const htmlPath = path.join(__dirname, '../../public/index.html');
  const html = fs.readFileSync(htmlPath, 'utf8');

  const setupIdx = html.indexOf('id="setupModal"');
  const extIdx = html.indexOf('id="addExternalCourseModal"');
  assert.ok(setupIdx > 0, 'setupModal not found in index.html');
  assert.ok(extIdx > 0, 'addExternalCourseModal not found in index.html');
  assert.ok(extIdx > setupIdx, 'addExternalCourseModal must come after setupModal in DOM');

  // Multi-select elements exist
  assert.ok(html.includes('id="extCourseTeachingsList"'), 'extCourseTeachingsList must exist');
  assert.ok(html.includes('id="btnExtSelectAll"'), 'btnExtSelectAll must exist');
  assert.ok(html.includes('id="btnAddAndContinueExternalCourse"'), 'btnAddAndContinueExternalCourse must exist');
});

test('External courses logic exposes multi-select and batch add capabilities', () => {
  assert.ok(typeof sandbox.openAddExternalCourseModal === 'function');
  assert.ok(typeof sandbox.confirmAddExternalCourse === 'function');
  assert.ok(typeof sandbox.onExtSelectAll === 'function');
  assert.ok(typeof sandbox.onExtDeselectAll === 'function');
  assert.ok(typeof sandbox.renderExtTeachingsList === 'function');
  assert.ok(typeof sandbox.updateExtActionButtons === 'function');
});

test('Google OAuth Campus Auth, Persistent Session badges, and GDPR Modal elements exist in HTML and CSS', () => {
  const htmlPath = path.join(__dirname, '../../public/index.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const cssPath = path.join(__dirname, '../../public/css/style.css');
  const css = fs.readFileSync(cssPath, 'utf8');

  // 1. Google Identity Services client script
  assert.ok(html.includes('https://accounts.google.com/gsi/client'), 'GSI script must be in head');

  // 2. Google sign-in container & test option
  assert.ok(html.includes('id="g_id_signin_container"'), 'Google container must exist');
  assert.ok(html.includes('id="testMockLoginAccordion"'), 'Test mock login accordion must exist');
  assert.ok(html.includes('id="mockAccountSelect"'), 'Mock account select must exist');
  assert.ok(html.includes('id="btnExecuteMockLogin"'), 'Execute mock login button must exist');

  // 3. Role badges and teacher shortcuts
  assert.ok(html.includes('id="profileRoleBadge"'), 'profileRoleBadge must exist');
  assert.ok(html.includes('id="profileTeacherQuickBox"'), 'profileTeacherQuickBox must exist');
  assert.ok(html.includes('id="btnProfileTeacherSchedule"'), 'btnProfileTeacherSchedule must exist');
  assert.strictEqual(
    html.includes('Sessione permanente: niente più login ripetuti'),
    false,
    'Old green badge text must be removed from login screen'
  );

  // 4. GDPR Privacy modal and disclaimer
  assert.ok(html.includes('id="privacyModal"'), 'privacyModal must exist');
  assert.ok(html.includes('id="btnOpenPrivacyModal"'), 'btnOpenPrivacyModal must exist');
  assert.ok(html.includes('id="btnWipeAccount"'), 'btnWipeAccount must exist');
  assert.ok(html.includes('id="profileAvatar"'), 'profileAvatar must exist');

  // 5. CSS classes for dual roles
  assert.ok(css.includes('.google-auth-container'), 'CSS must include .google-auth-container');
  assert.ok(css.includes('.google-auth-badge'), 'CSS must include .google-auth-badge');
  assert.ok(css.includes('.persistent-session-badge'), 'CSS must include .persistent-session-badge');
  assert.ok(css.includes('.legal-card'), 'CSS must include .legal-card');
  assert.ok(css.includes('.profile-avatar-circle'), 'CSS must include .profile-avatar-circle');
  assert.ok(css.includes('.profile-role-badge.student'), 'CSS must include student role badge');
  assert.ok(css.includes('.profile-role-badge.professor'), 'CSS must include professor role badge');
  assert.ok(css.includes('.profile-avatar-circle.student'), 'CSS must include student avatar styling');
  assert.ok(css.includes('.profile-avatar-circle.professor'), 'CSS must include professor avatar styling');
  assert.ok(css.includes('#btnProfile.is-student'), 'CSS must include #btnProfile.is-student');
  assert.ok(css.includes('#btnProfile.is-professor'), 'CSS must include #btnProfile.is-professor');
});

test('Google auth, role separation, and GDPR handler functions are defined in app.js', () => {
  assert.ok(typeof sandbox.initGoogleAuthUi === 'function');
  assert.ok(typeof sandbox.handleGoogleAuthCredential === 'function');
  assert.ok(typeof sandbox.handleMockGoogleLogin === 'function');
  assert.ok(typeof sandbox.handleMockStudentLogin === 'function');
  assert.ok(typeof sandbox.handleMockProfessorLogin === 'function');
  assert.ok(typeof sandbox.handleOpenTeacherSchedule === 'function');
  assert.ok(typeof sandbox.handleWipeAccount === 'function');
  assert.ok(typeof sandbox.refreshSessionInBackground === 'function');
});

test('handleMockStudentLogin and handleMockProfessorLogin populate profileState correctly even offline', async () => {
  // Mock fetch to simulate 404/network error as in static server
  sandbox.fetch = async () => { throw new Error('Failed to fetch /api/profile'); };
  const state = vm.runInContext('state', context);
  state.config = { anno: '2026', corso: 'F1801Q' };

  // 1. Student Mock Login
  await sandbox.handleMockStudentLogin();
  const profileState = vm.runInContext('profileState', context);
  assert.strictEqual(profileState.role, 'student');
  assert.strictEqual(profileState.email, 'm.rossi@campus.unimib.it');
  assert.strictEqual(profileState.nickname, 'Mario Rossi');
  assert.ok(profileState.shareCode);

  // 2. Professor Mock Login
  await sandbox.handleMockProfessorLogin();
  assert.strictEqual(profileState.role, 'professor');
  assert.strictEqual(profileState.email, 'mario.rossi@unimib.it');
  assert.strictEqual(profileState.nickname, 'Prof. Mario Rossi');

  // 3. Unauthorized domain rejection in mock token
  let errorMsg = '';
  sandbox.document.getElementById = (id) => {
    if (id === 'googleAuthError') {
      return {
        style: {},
        set textContent(v) { errorMsg = v; },
        get textContent() { return errorMsg; }
      };
    }
    return mockElement();
  };
  await sandbox.handleGoogleAuthCredential({
    credential: 'mock_google_token:external@gmail.com:123:External User'
  });
  assert.ok(errorMsg.includes('@campus.unimib.it'), 'Must reject non-unimib domains');
});

test('Professor UI elements and modals exist in index.html and style.css', () => {
  const htmlPath = path.join(__dirname, '../../public/index.html');
  const cssPath = path.join(__dirname, '../../public/css/style.css');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const css = fs.readFileSync(cssPath, 'utf8');

  // professorTimetableSection must be located within viewTeachers, NOT viewTimetable
  const idxViewTimetable = html.indexOf('id="viewTimetable"');
  const idxViewTeachers = html.indexOf('id="viewTeachers"');
  const idxProfSection = html.indexOf('id="professorTimetableSection"');
  const idxStdSearch = html.indexOf('id="teachersStandardSearchSection"');

  assert.ok(idxProfSection > idxViewTeachers, 'professorTimetableSection must be inside viewTeachers');
  assert.ok(idxStdSearch > idxViewTeachers, 'teachersStandardSearchSection must be inside viewTeachers');
  assert.ok(html.includes('id="btnProfToggleColleagueSearch"'));

  // Ensure viewTimetable does not contain professorTimetableSection
  const timetableChunk = html.slice(idxViewTimetable, idxViewTeachers);
  assert.ok(!timetableChunk.includes('id="professorTimetableSection"'), 'viewTimetable must not contain professorTimetableSection');

  // Professor presentation card and controls
  assert.ok(html.includes('id="professorHeaderCard"'));
  assert.ok(html.includes('id="profAvatarCircle"'));
  assert.ok(html.includes('id="profHeaderName"'));
  assert.ok(html.includes('id="profHeaderEmail"'));
  assert.ok(html.includes('id="profLessonsCountBadge"'));
  assert.ok(html.includes('id="btnProfExportIcs"'));
  assert.ok(html.includes('id="btnProfRefreshSchedule"'));
  assert.ok(html.includes('id="btnProfChangeTeacher"'));
  assert.ok(html.includes('id="profLessonSearchInput"'));
  assert.ok(html.includes('id="profUnifiedLessonsContainer"'));

  // Modals for teacher note and teacher association
  assert.ok(html.includes('id="teacherNoteModal"'));
  assert.ok(html.includes('id="teacherNoteTextInput"'));
  assert.ok(html.includes('id="btnSaveTeacherNote"'));
  assert.ok(html.includes('id="teacherAssociateModal"'));
  assert.ok(html.includes('id="teacherAssociateSearchInput"'));

  // CSS classes for professor card, banners and month/week grouping
  assert.ok(css.includes('.professor-profile-card'));
  assert.ok(css.includes('.prof-lesson-card'));
  assert.ok(css.includes('.event-teacher-note-banner'));
  assert.ok(css.includes('.event-designated-teacher-banner'));
  assert.ok(css.includes('.prof-month-section'));
  assert.ok(css.includes('.prof-month-header'));
  assert.ok(css.includes('.prof-month-title'));
  assert.ok(css.includes('.prof-week-card'));
  assert.ok(css.includes('.prof-week-header'));
  assert.ok(css.includes('.prof-week-title'));
});

test('Teacher notes and designated teacher state management work in app.js', async () => {
  const saveTeacherNote = sandbox.saveTeacherNote;
  const deleteTeacherNote = sandbox.deleteTeacherNote;
  const getTeacherNoteFor = sandbox.getTeacherNoteFor;
  const saveDesignatedTeacher = sandbox.saveDesignatedTeacher;
  const getDesignatedTeacherFor = sandbox.getDesignatedTeacherFor;

  assert.ok(typeof saveTeacherNote === 'function');
  assert.ok(typeof deleteTeacherNote === 'function');
  assert.ok(typeof getTeacherNoteFor === 'function');
  assert.ok(typeof saveDesignatedTeacher === 'function');
  assert.ok(typeof getDesignatedTeacherFor === 'function');

  // Save lesson-specific note
  await saveTeacherNote({
    courseCode: 'F1001',
    lessonId: 'lesson_test_123',
    note: 'Portare il laptop in aula',
    authorName: 'Prof. Rossi'
  });

  const note = getTeacherNoteFor('F1001', 'lesson_test_123');
  assert.ok(note);
  assert.strictEqual(note.note, 'Portare il laptop in aula');
  assert.strictEqual(note.author, 'Prof. Rossi');

  // Designated teacher for co-docenza
  await saveDesignatedTeacher({
    lessonId: 'lesson_test_123',
    teacherName: 'Prof.ssa Laura Bianchi',
    authorName: 'Prof. Rossi'
  });

  const des = getDesignatedTeacherFor('lesson_test_123');
  assert.strictEqual(des, 'Prof.ssa Laura Bianchi');

  // Delete note
  await deleteTeacherNote({
    courseCode: 'F1001',
    lessonId: 'lesson_test_123'
  });
  const afterDel = getTeacherNoteFor('F1001', 'lesson_test_123');
  assert.strictEqual(afterDel, null);
});

test('parseTeachersList extracts multiple co-teachers reliably', () => {
  const parseTeachersList = sandbox.parseTeachersList;
  assert.ok(typeof parseTeachersList === 'function');

  const single = parseTeachersList('Prof. Mario Rossi');
  assert.deepStrictEqual(Array.from(single), ['Prof. Mario Rossi']);

  const commaSeparated = parseTeachersList('Prof. Mario Rossi, Prof.ssa Laura Bianchi');
  assert.deepStrictEqual(Array.from(commaSeparated), ['Prof. Mario Rossi', 'Prof.ssa Laura Bianchi']);

  const italianConjunction = parseTeachersList('Prof. Mario Rossi e Prof. Giuseppe Verdi');
  assert.deepStrictEqual(Array.from(italianConjunction), ['Prof. Mario Rossi', 'Prof. Giuseppe Verdi']);
});

test('getMockProfessorLessons returns realistic unified teaching schedule', () => {
  const getMockProfessorLessons = sandbox.getMockProfessorLessons;
  assert.ok(typeof getMockProfessorLessons === 'function');

  const lessons = getMockProfessorLessons('Prof. Mario Rossi');
  assert.ok(Array.isArray(lessons));
  assert.ok(lessons.length >= 8);

  const first = lessons[0];
  assert.ok(first.id);
  assert.ok(first.date);
  assert.ok(first.course);
  assert.ok(first.docente.includes('Prof. Mario Rossi'));
});

test('generateIcs and generateCsv embed designated_teacher and teacher_note in exports', () => {
  const generateIcs = sandbox.generateIcs;
  const generateCsv = sandbox.generateCsv;

  const mockEvents = [{
    id: 'ev_prof_export_1',
    date: '2026-10-20',
    start_time: '09:30',
    end_time: '11:30',
    course: 'Programmazione I',
    course_code: 'F1001',
    aula: 'U1-01',
    docente: 'Prof. Mario Rossi, Prof.ssa Laura Bianchi',
    designated_teacher: 'Prof.ssa Laura Bianchi',
    teacher_note: 'Lezione su ereditarietà e polimorfismo'
  }];

  const ics = generateIcs(mockEvents, 'Cattedra Rossi');
  assert.ok(ics.includes('BEGIN:VCALENDAR'));
  assert.ok(ics.includes('Docente per questa lezione: Prof.ssa Laura Bianchi'));
  assert.ok(ics.includes('Nota Docente: Lezione su ereditarietà e polimorfismo'));

  const csv = generateCsv(mockEvents);
  assert.ok(csv.includes('Docente per questa lezione: Prof.ssa Laura Bianchi'));
  assert.ok(csv.includes('Nota Docente: Lezione su ereditarietà e polimorfismo'));
});

test('formatWeekRangeLabel and getLessonsForWeek compute weekly ranges correctly', () => {
  const formatWeekRangeLabel = sandbox.formatWeekRangeLabel;
  const getLessonsForWeek = sandbox.getLessonsForWeek;

  assert.ok(typeof formatWeekRangeLabel === 'function');
  assert.ok(typeof getLessonsForWeek === 'function');

  const label = formatWeekRangeLabel('19-10-2026');
  assert.ok(label.includes('19') && label.includes('23') && label.includes('2026'));

  const lessons = [
    { id: 'l1', date: '19-10-2026', course: 'L1' },
    { id: 'l2', date: '2026-10-21', course: 'L2' },
    { id: 'l3', date: '26-10-2026', course: 'L3' } // next week
  ];

  const weekEvents = getLessonsForWeek(lessons, '19-10-2026');
  assert.strictEqual(weekEvents.length, 2);
  assert.strictEqual(weekEvents[0].id, 'l1');
  assert.strictEqual(weekEvents[1].id, 'l2');
});

test('loadProfessorWeeklyCalendar sets state.calendarData with 5 working days for professor Orario view', () => {
  const loadProfessorWeeklyCalendar = sandbox.loadProfessorWeeklyCalendar;
  const state = vm.runInContext('state', context);
  const profState = vm.runInContext('professorScheduleState', context);

  assert.ok(typeof loadProfessorWeeklyCalendar === 'function');

  profState.lessons = [
    { id: 'lp1', date: '19-10-2026', course: 'Corso A', start_time: '09:00', end_time: '11:00' },
    { id: 'lp2', date: '20-10-2026', course: 'Corso B', start_time: '14:00', end_time: '16:00' }
  ];

  loadProfessorWeeklyCalendar('19-10-2026', false);

  assert.strictEqual(state.currentMonday, '19-10-2026');
  assert.ok(state.calendarData);
  assert.strictEqual(state.calendarData.events.length, 2);
  assert.strictEqual(state.calendarData.giorni.length, 5);
  assert.strictEqual(state.calendarData.giorni[0].name, 'LUN');
  assert.strictEqual(state.calendarData.giorni[0].data, '19-10-2026');
  assert.strictEqual(state.calendarData.giorni[0].date, '19-10-2026');
  assert.ok(state.calendarData.giorni[0].label.includes('Lunedì'));
  assert.strictEqual(state.calendarData.giorni[4].name, 'VEN');
  assert.strictEqual(state.calendarData.giorni[4].data, '23-10-2026');
  assert.ok(state.calendarData.week_label);
});

test('renderProfessorTimetable groups lessons hierarchically by Month and Week', () => {
  const renderProfessorTimetable = sandbox.renderProfessorTimetable;
  const profState = vm.runInContext('professorScheduleState', context);

  assert.ok(typeof renderProfessorTimetable === 'function');

  // Provide mock lessons spanning two different months and weeks
  profState.lessons = [
    { id: 'm1_w1', date: '12-10-2026', course: 'Oct W1', start_time: '09:00', end_time: '11:00', docente: 'Prof. Mario Rossi' },
    { id: 'm1_w2', date: '19-10-2026', course: 'Oct W2', start_time: '09:00', end_time: '11:00', docente: 'Prof. Mario Rossi' },
    { id: 'm2_w1', date: '02-11-2026', course: 'Nov W1', start_time: '09:00', end_time: '11:00', docente: 'Prof. Mario Rossi' }
  ];
  profState.searchQuery = '';
  profState.timeScope = 'all';
  profState.selectedMonth = 'all';

  const appendedMonths = [];
  const mockContainer = {
    innerHTML: '',
    appendChild: (child) => {
      appendedMonths.push(child);
    }
  };

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'profUnifiedLessonsContainer') return mockContainer;
    return mockElement();
  };

  try {
    renderProfessorTimetable();
    assert.strictEqual(appendedMonths.length, 2, 'Should create 2 month sections');
    assert.strictEqual(appendedMonths[0].className, 'prof-month-section');
    assert.strictEqual(appendedMonths[1].className, 'prof-month-section');
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('updateTimetableForRole toggles colleague search for professor', () => {
  const updateTimetableForRole = sandbox.updateTimetableForRole;
  const profileState = vm.runInContext('profileState', context);
  const profState = vm.runInContext('professorScheduleState', context);

  assert.ok(typeof updateTimetableForRole === 'function');

  profileState.role = 'professor';
  profState.showColleagueSearch = false;

  const profSection = mockElement();
  const stdSearchSection = mockElement();
  const toggleBtn = mockElement();

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'professorTimetableSection') return profSection;
    if (id === 'teachersStandardSearchSection') return stdSearchSection;
    if (id === 'btnProfToggleColleagueSearch') return toggleBtn;
    return mockElement();
  };

  try {
    updateTimetableForRole();
    assert.strictEqual(profSection.style.display, 'block');
    assert.strictEqual(stdSearchSection.style.display, 'none');

    // Toggle colleague search to true
    profState.showColleagueSearch = true;
    updateTimetableForRole();
    assert.strictEqual(stdSearchSection.style.display, 'block');
    assert.ok(toggleBtn.innerHTML.includes('Chiudi'));
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('renderEvents displays professor courses without crashing on null config or missing favorites', () => {
  const renderEvents = sandbox.renderEvents;
  const state = vm.runInContext('state', context);
  const profileState = vm.runInContext('profileState', context);

  assert.ok(typeof renderEvents === 'function');

  profileState.role = 'professor';
  state.config = null; // simulate professor with no student config
  state.favoriteColors = {};
  state.activeFilter = 'target';
  state.searchQuery = '';
  state.selectedDayDate = 'all';
  state.calendarData = {
    events: [
      {
        id: 'prof_ev_1',
        date: '19-10-2026',
        day_name: 'Lunedì',
        start_time: '09:30',
        end_time: '11:30',
        course: 'Programmazione I',
        course_code: 'F1001',
        aula: 'U1-01',
        docente: 'Prof. Mario Rossi'
      }
    ],
    giorni: []
  };

  const appendedSections = [];
  const mockContainer = {
    innerHTML: '',
    appendChild: (section) => {
      appendedSections.push(section);
    }
  };

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'eventsContainer') return mockContainer;
    return mockElement();
  };

  try {
    renderEvents();
    assert.strictEqual(appendedSections.length, 1, 'Must render day section for professor lesson');
    assert.strictEqual(appendedSections[0].className, 'day-section');
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('updateTimetableForRole swaps student toggle group with professor info banner', () => {
  const updateTimetableForRole = sandbox.updateTimetableForRole;
  const profileState = vm.runInContext('profileState', context);

  const filterToggle = mockElement();
  const profBanner = mockElement();
  const searchInput = mockElement();

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'timetableFilterToggleGroup') return filterToggle;
    if (id === 'profTimetableInfoBanner') return profBanner;
    if (id === 'searchInput') return searchInput;
    return mockElement();
  };

  try {
    profileState.role = 'professor';
    updateTimetableForRole();
    assert.strictEqual(filterToggle.style.display, 'none');
    assert.strictEqual(profBanner.style.display, 'flex');
    assert.ok(searchInput.placeholder.includes('tuoi corsi'));

    profileState.role = 'student';
    updateTimetableForRole();
    assert.strictEqual(filterToggle.style.display, 'flex');
    assert.strictEqual(profBanner.style.display, 'none');
    assert.ok(searchInput.placeholder.includes('docente o aula'));
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('Day selection in Orario works properly for professor schedule', () => {
  const renderDayTabs = sandbox.renderDayTabs;
  const renderEvents = sandbox.renderEvents;
  const state = vm.runInContext('state', context);
  const profileState = vm.runInContext('profileState', context);

  profileState.role = 'professor';
  state.selectedDayDate = 'all';
  state.calendarData = {
    events: [
      { id: 'ev_mon', date: '19-10-2026', course: 'Programmazione I', course_code: 'F1001', start_time: '09:00', end_time: '11:00' },
      { id: 'ev_tue', date: '20-10-2026', course: 'Algoritmi', course_code: 'F1002', start_time: '11:00', end_time: '13:00' }
    ],
    giorni: [
      { name: 'LUN', label: 'Lunedì 19', data: '19-10-2026', date: '19-10-2026' },
      { name: 'MAR', label: 'Martedì 20', data: '20-10-2026', date: '20-10-2026' },
      { name: 'MER', label: 'Mercoledì 21', data: '21-10-2026', date: '21-10-2026' },
      { name: 'GIO', label: 'Giovedì 22', data: '22-10-2026', date: '22-10-2026' },
      { name: 'VEN', label: 'Venerdì 23', data: '23-10-2026', date: '23-10-2026' }
    ],
    week_label: '19 - 23 Ottobre 2026'
  };

  const createdTabs = [];
  const mockTabsContainer = {
    innerHTML: '',
    setAttribute: () => {},
    appendChild: (t) => createdTabs.push(t),
    querySelector: () => mockElement()
  };

  const appendedSections = [];
  const mockEventsContainer = {
    innerHTML: '',
    appendChild: (s) => appendedSections.push(s)
  };

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'daysTabBar') return mockTabsContainer;
    if (id === 'eventsContainer') return mockEventsContainer;
    return mockElement();
  };

  try {
    renderDayTabs();
    assert.strictEqual(createdTabs.length, 6, 'Must generate TUTTI + 5 days');

    // Monday tab is index 1
    const mondayTab = createdTabs[1];
    assert.ok(mondayTab.innerHTML.includes('LUN'));
    assert.ok(mondayTab.innerHTML.includes('19'));

    // Trigger click on Monday tab
    mondayTab.click();
    assert.strictEqual(state.selectedDayDate, '19-10-2026');

    // Verify events render only Monday
    appendedSections.length = 0;
    renderEvents();
    assert.strictEqual(appendedSections.length, 1);

    // Trigger click on TUTTI tab (index 0)
    createdTabs[0].click();
    assert.strictEqual(state.selectedDayDate, 'all');

    // Verify events render all days
    appendedSections.length = 0;
    renderEvents();
    assert.strictEqual(appendedSections.length, 2);
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('isCourseTaughtByCurrentProfessor validates course code, title and role correctly', () => {
  const isCourseTaughtByCurrentProfessor = sandbox.isCourseTaughtByCurrentProfessor;
  const profileState = vm.runInContext('profileState', context);
  const professorScheduleState = vm.runInContext('professorScheduleState', context);

  // 1. Student role cannot teach any course
  profileState.role = 'student';
  professorScheduleState.lessons = [
    { id: 'l1', course_code: 'F1001', course: 'Programmazione I' }
  ];
  assert.strictEqual(isCourseTaughtByCurrentProfessor('F1001', 'Programmazione I', 'l1'), false);

  // 2. Professor role matches taught course code or title
  profileState.role = 'professor';
  assert.strictEqual(isCourseTaughtByCurrentProfessor('F1001', 'Programmazione I', 'l1'), true);
  assert.strictEqual(isCourseTaughtByCurrentProfessor('F1001', '', ''), true);
  assert.strictEqual(isCourseTaughtByCurrentProfessor('', 'Programmazione I', ''), true);

  // 3. Course not taught by current professor evaluates to false
  assert.strictEqual(isCourseTaughtByCurrentProfessor('F9999', 'Fisica Quantistica', 'other_id'), false);
});

test('getVisibleTeacherNoteFor and getVisibleDesignatedTeacherFor restrict data to taught courses only', async () => {
  const saveTeacherNote = sandbox.saveTeacherNote;
  const saveDesignatedTeacher = sandbox.saveDesignatedTeacher;
  const getVisibleTeacherNoteFor = sandbox.getVisibleTeacherNoteFor;
  const getVisibleDesignatedTeacherFor = sandbox.getVisibleDesignatedTeacherFor;
  const profileState = vm.runInContext('profileState', context);
  const professorScheduleState = vm.runInContext('professorScheduleState', context);

  await saveTeacherNote({
    courseCode: 'F1001',
    lessonId: 'lesson_auth_1',
    note: 'Nota riservata ai docenti del corso',
    authorName: 'Prof. Rossi'
  });
  await saveDesignatedTeacher({
    lessonId: 'lesson_auth_1',
    teacherName: 'Prof.ssa Bianchi',
    authorName: 'Prof. Rossi'
  });

  // A. Student cannot see them
  profileState.role = 'student';
  professorScheduleState.lessons = [{ id: 'lesson_auth_1', course_code: 'F1001', course: 'Programmazione I' }];
  assert.strictEqual(getVisibleTeacherNoteFor('F1001', 'lesson_auth_1', 'Programmazione I'), null);
  assert.strictEqual(getVisibleDesignatedTeacherFor('lesson_auth_1', 'F1001', 'Programmazione I'), null);

  // B. Unauthorized professor (does not teach F1001) cannot see them
  profileState.role = 'professor';
  professorScheduleState.lessons = [{ id: 'lesson_diff_2', course_code: 'F2002', course: 'Statistica' }];
  assert.strictEqual(getVisibleTeacherNoteFor('F1001', 'lesson_auth_1', 'Programmazione I'), null);
  assert.strictEqual(getVisibleDesignatedTeacherFor('lesson_auth_1', 'F1001', 'Programmazione I'), null);

  // C. Authorized professor teaching F1001 CAN see them
  professorScheduleState.lessons = [
    { id: 'lesson_auth_1', course_code: 'F1001', course: 'Programmazione I' }
  ];
  const visibleNote = getVisibleTeacherNoteFor('F1001', 'lesson_auth_1', 'Programmazione I');
  assert.ok(visibleNote);
  assert.strictEqual(visibleNote.note, 'Nota riservata ai docenti del corso');

  const visibleTeacher = getVisibleDesignatedTeacherFor('lesson_auth_1', 'F1001', 'Programmazione I');
  assert.strictEqual(visibleTeacher, 'Prof.ssa Bianchi');
});

test('renderEvents displays teacher note and designated teacher in Orario ONLY for authorized professors in read-only mode', () => {
  const renderEvents = sandbox.renderEvents;
  const state = vm.runInContext('state', context);
  const profileState = vm.runInContext('profileState', context);
  const professorScheduleState = vm.runInContext('professorScheduleState', context);
  const teacherNotesState = vm.runInContext('teacherNotesState', context);

  teacherNotesState.courseNotes['F1001'] = { note: 'Nota visibile solo ai docenti', author: 'Prof. Rossi' };
  teacherNotesState.designatedTeachers['ev_orario_1'] = 'Prof.ssa Laura Bianchi';

  state.activeFilter = 'all';
  state.selectedDayDate = 'all';
  state.calendarData = {
    events: [
      { id: 'ev_orario_1', date: '19-10-2026', course: 'Programmazione I', course_code: 'F1001', start_time: '09:00', end_time: '11:00' }
    ],
    giorni: [
      { name: 'LUN', label: 'Lunedì 19', data: '19-10-2026', date: '19-10-2026' }
    ]
  };

  const appendedSections = [];
  const mockEventsContainer = {
    innerHTML: '',
    appendChild: (s) => appendedSections.push(s)
  };

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'eventsContainer') return mockEventsContainer;
    return mockElement();
  };

  try {
    // 1. Case: Student views Orario -> notes and designated teacher must NOT be rendered
    profileState.role = 'student';
    professorScheduleState.lessons = [];
    appendedSections.length = 0;
    renderEvents();
    assert.strictEqual(appendedSections.length, 1);
    const studentCard = appendedSections[0].children[0];
    const studentCardHtml = studentCard ? studentCard.innerHTML : '';
    assert.ok(!studentCardHtml.includes('event-designated-teacher-banner'), 'Student must not see designated teacher banner');
    assert.ok(!studentCardHtml.includes('event-teacher-note-banner'), 'Student must not see teacher note banner');
    assert.ok(!studentCardHtml.includes('Prof.ssa Laura Bianchi'), 'Student must not see designated teacher text');
    assert.ok(!studentCardHtml.includes('Nota visibile solo ai docenti'), 'Student must not see teacher note text');

    // 2. Case: Professor NOT teaching the course -> must NOT be rendered
    profileState.role = 'professor';
    professorScheduleState.lessons = [{ id: 'other_l', course_code: 'F9000', course: 'Chimica' }];
    appendedSections.length = 0;
    renderEvents();
    const unauthProfCard = appendedSections[0].children[0];
    const unauthProfCardHtml = unauthProfCard ? unauthProfCard.innerHTML : '';
    assert.ok(!unauthProfCardHtml.includes('event-designated-teacher-banner'));
    assert.ok(!unauthProfCardHtml.includes('event-teacher-note-banner'));

    // 3. Case: Professor teaching the course -> MUST be rendered in read-only form
    professorScheduleState.lessons = [{ id: 'ev_orario_1', course_code: 'F1001', course: 'Programmazione I' }];
    appendedSections.length = 0;
    renderEvents();
    const authProfCard = appendedSections[0].children[0];
    const authProfCardHtml = authProfCard ? authProfCard.innerHTML : '';
    assert.ok(authProfCardHtml.includes('event-designated-teacher-banner'), 'Authorized professor must see designated teacher banner');
    assert.ok(authProfCardHtml.includes('event-teacher-note-banner'), 'Authorized professor must see teacher note banner');
    assert.ok(authProfCardHtml.includes('Prof.ssa Laura Bianchi'));
    assert.ok(authProfCardHtml.includes('Nota visibile solo ai docenti'));

    // 4. Must be strictly read-only: no edit button or select dropdown in the banner or card top
    assert.ok(!authProfCardHtml.includes('btn-edit-teacher-note'), 'Orario must not include edit note button');
    assert.ok(!authProfCardHtml.includes('prof-co-teacher-select'), 'Orario must not include co-teacher select dropdown');
    assert.ok(!authProfCardHtml.includes('<select'), 'Orario card must be strictly read-only');
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('generateIcs and generateCsv hide notes from students but show to authorized professors', () => {
  const generateIcs = sandbox.generateIcs;
  const generateCsv = sandbox.generateCsv;
  const profileState = vm.runInContext('profileState', context);
  const professorScheduleState = vm.runInContext('professorScheduleState', context);
  const teacherNotesState = vm.runInContext('teacherNotesState', context);

  teacherNotesState.courseNotes['F1001'] = { note: 'Promemoria docenti per esonero', author: 'Prof. Rossi' };
  teacherNotesState.designatedTeachers['ev_exp_1'] = 'Prof. Mario Rossi';

  const events = [{
    id: 'ev_exp_1',
    date: '2026-10-20',
    start_time: '09:00',
    end_time: '11:00',
    course: 'Programmazione I',
    course_code: 'F1001',
    aula: 'U1-01',
    docente: 'Prof. Mario Rossi, Prof.ssa Laura Bianchi'
  }];

  // 1. Student export: no private teacher info
  profileState.role = 'student';
  professorScheduleState.lessons = [];
  const icsStudent = generateIcs(events);
  const csvStudent = generateCsv(events);
  assert.ok(!icsStudent.includes('Docente per questa lezione:'));
  assert.ok(!icsStudent.includes('Nota Docente:'));
  assert.ok(!csvStudent.includes('Docente per questa lezione:'));
  assert.ok(!csvStudent.includes('Nota Docente:'));

  // 2. Authorized professor export: includes private teacher info
  profileState.role = 'professor';
  professorScheduleState.lessons = events;
  const icsProf = generateIcs(events);
  const csvProf = generateCsv(events);
  assert.ok(icsProf.includes('Docente per questa lezione: Prof. Mario Rossi'));
  assert.ok(icsProf.includes('Nota Docente: Promemoria docenti per esonero'));
  assert.ok(csvProf.includes('Docente per questa lezione: Prof. Mario Rossi'));
  assert.ok(csvProf.includes('Nota Docente: Promemoria docenti per esonero'));
});

test('renderProfessorTimetable starts from current date by default and respects timeScope (upcoming, past, all)', () => {
  const renderProfessorTimetable = sandbox.renderProfessorTimetable;
  const profState = vm.runInContext('professorScheduleState', context);

  const today = new Date();
  const pastDate = new Date(today);
  pastDate.setDate(today.getDate() - 10);
  const pastDateStr = `${String(pastDate.getDate()).padStart(2, '0')}-${String(pastDate.getMonth() + 1).padStart(2, '0')}-${pastDate.getFullYear()}`;

  const upcomingDate1 = new Date(today);
  upcomingDate1.setDate(today.getDate() + 2);
  const up1DateStr = `${String(upcomingDate1.getDate()).padStart(2, '0')}-${String(upcomingDate1.getMonth() + 1).padStart(2, '0')}-${upcomingDate1.getFullYear()}`;

  const upcomingDate2 = new Date(today);
  upcomingDate2.setDate(today.getDate() + 8);
  const up2DateStr = `${String(upcomingDate2.getDate()).padStart(2, '0')}-${String(upcomingDate2.getMonth() + 1).padStart(2, '0')}-${upcomingDate2.getFullYear()}`;

  profState.lessons = [
    { id: 'les_past', date: pastDateStr, course: 'Past Course', start_time: '09:00', end_time: '11:00', docente: 'Prof. Mario Rossi' },
    { id: 'les_up1', date: up1DateStr, course: 'Upcoming Course 1', start_time: '11:30', end_time: '13:30', docente: 'Prof. Mario Rossi' },
    { id: 'les_up2', date: up2DateStr, course: 'Upcoming Course 2', start_time: '14:30', end_time: '16:30', docente: 'Prof. Mario Rossi' }
  ];
  profState.searchQuery = '';
  profState.timeScope = 'all';
  profState.selectedMonth = 'all';
  profState.selectedMonth = 'all';

  let heroChild = null;
  let toolbarChild = null;
  const appendedSections = [];

  const mockHeroContainer = {
    innerHTML: '',
    appendChild: (child) => { heroChild = child; }
  };
  const mockControlsContainer = {
    innerHTML: '',
    appendChild: (child) => { toolbarChild = child; }
  };
  const mockContainer = {
    innerHTML: '',
    appendChild: (child) => { appendedSections.push(child); }
  };

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'profHeroContainer') return mockHeroContainer;
    if (id === 'profControlsContainer') return mockControlsContainer;
    if (id === 'profUnifiedLessonsContainer') return mockContainer;
    return mockElement();
  };

  try {
    // 1. Default: timeScope = upcoming -> only upcoming lessons, hero card present
    profState.timeScope = 'upcoming';
    renderProfessorTimetable();

    assert.ok(heroChild !== null, 'Hero card should be rendered for next lesson');
    assert.strictEqual(heroChild.className, 'prof-hero-card');
    assert.ok(toolbarChild !== null, 'Controls toolbar should be rendered');
    assert.strictEqual(toolbarChild.className, 'prof-controls-toolbar');
    assert.ok(appendedSections.length > 0, 'Should render upcoming month sections');

    // 2. Switch to past: timeScope = past -> only past lessons, hero card absent
    heroChild = null;
    appendedSections.length = 0;
    profState.timeScope = 'past';
    renderProfessorTimetable();

    assert.strictEqual(heroChild, null, 'Hero card should not be displayed in past scope');
    assert.ok(appendedSections.length > 0, 'Should render past month section');

    // 3. Switch to all: timeScope = all -> includes both past and upcoming
    heroChild = null;
    appendedSections.length = 0;
    profState.timeScope = 'all';
    renderProfessorTimetable();

    assert.ok(heroChild !== null, 'Hero card should be displayed in all scope');
    assert.ok(appendedSections.length > 0, 'Should render month sections for all lessons');
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('createProfessorControlsToolbar renders scope buttons and month navigation pills', () => {
  const createProfessorControlsToolbar = sandbox.createProfessorControlsToolbar;
  const profState = vm.runInContext('professorScheduleState', context);

  assert.ok(typeof createProfessorControlsToolbar === 'function');

  profState.timeScope = 'upcoming';
  profState.selectedMonth = 'all';

  const toolbar = createProfessorControlsToolbar({
    upcomingCount: 5,
    totalCount: 12,
    pastCount: 7,
    sortedMonthKeys: ['2026-10', '2026-11'],
    monthGroups: {
      '2026-10': { label: 'Ottobre 2026', lessons: [1, 2, 3] },
      '2026-11': { label: 'Novembre 2026', lessons: [4, 5] }
    }
  });

  assert.ok(toolbar, 'Toolbar element should be created');
  assert.strictEqual(toolbar.className, 'prof-controls-toolbar');
  assert.ok(toolbar.innerHTML.includes('Da oggi in poi (5)'));
  assert.ok(toolbar.innerHTML.includes('Tutte (12)'));
  assert.ok(toolbar.innerHTML.includes('Passate (7)'));
  assert.ok(toolbar.innerHTML.includes('prof-month-pills-bar'));
  assert.ok(toolbar.innerHTML.includes('Ottobre 2026 (3)'));
  assert.ok(toolbar.innerHTML.includes('Novembre 2026 (2)'));
});

test('parseAnyDate handles various formats, slashes, whitespace, and leap years', () => {
  const parseAnyDate = sandbox.parseAnyDate;

  // 1. Hyphen formats
  const d1 = parseAnyDate('2026-10-15');
  assert.strictEqual(d1.getFullYear(), 2026);
  assert.strictEqual(d1.getMonth(), 9);
  assert.strictEqual(d1.getDate(), 15);

  const d2 = parseAnyDate('15-10-2026');
  assert.strictEqual(d2.getFullYear(), 2026);
  assert.strictEqual(d2.getMonth(), 9);
  assert.strictEqual(d2.getDate(), 15);

  // 2. Slash formats
  const d3 = parseAnyDate('15/10/2026');
  assert.strictEqual(d3.getFullYear(), 2026);
  assert.strictEqual(d3.getMonth(), 9);
  assert.strictEqual(d3.getDate(), 15);

  const d4 = parseAnyDate('2026/10/15');
  assert.strictEqual(d4.getFullYear(), 2026);
  assert.strictEqual(d4.getMonth(), 9);
  assert.strictEqual(d4.getDate(), 15);

  // 3. Whitespace padding
  const d5 = parseAnyDate('  25-12-2026  ');
  assert.strictEqual(d5.getFullYear(), 2026);
  assert.strictEqual(d5.getMonth(), 11);
  assert.strictEqual(d5.getDate(), 25);

  // 4. Leap year
  const leap = parseAnyDate('29-02-2028');
  assert.strictEqual(leap.getFullYear(), 2028);
  assert.strictEqual(leap.getMonth(), 1); // February
  assert.strictEqual(leap.getDate(), 29);
});

test('generateCsv neutralizes spreadsheet formula injection and generateIcs escapes CRLF', () => {
  const generateCsv = sandbox.generateCsv;
  const generateIcs = sandbox.generateIcs;

  const maliciousEvents = [{
    id: 'ev_inj_1',
    date: '2026-10-20',
    start_time: '09:00',
    end_time: '11:00',
    course: '=cmd|"/C calc"!A0',
    docente: 'Prof. Rossi',
    aula: '+U1-01'
  }, {
    id: 'ev_inj_2',
    date: '2026-10-21',
    start_time: '09:00',
    end_time: '11:00',
    course: '-NegativeCourse',
    docente: 'Prof. Bianchi',
    aula: '@AtLocation'
  }];

  // 1. CSV Formula Injection check: cells starting with =, +, -, @ must be prefixed with '
  const csv = generateCsv(maliciousEvents);
  assert.ok(csv.includes("'\=cmd|"), 'Formula = must be escaped with single quote');
  assert.ok(csv.includes("'+U1-01"), 'Formula + must be escaped with single quote');
  assert.ok(csv.includes("'-NegativeCourse"), 'Formula - must be escaped with single quote');
  assert.ok(csv.includes("'@AtLocation"), 'Formula @ must be escaped with single quote');

  // 2. ICS CRLF injection check
  const crlfEvents = [{
    id: 'ev_crlf_1',
    date: '2026-10-20',
    start_time: '09:00',
    end_time: '11:00',
    course: "Titolo Lezione\r\nINJECTED_HEADER:EVIL",
    aula: "Aula U1\rAttacco"
  }];
  const ics = generateIcs(crlfEvents);
  // Must not have unescaped CRLF inside SUMMARY or LOCATION
  assert.ok(!ics.includes('SUMMARY:Titolo Lezione\r\nINJECTED_HEADER'), 'CRLF must be escaped');
  assert.ok(ics.includes('SUMMARY:Titolo Lezione\\nINJECTED_HEADER'), 'CRLF must be converted to \\n');
  assert.ok(ics.includes('LOCATION:Aula U1\\nAttacco'), 'CR must be converted to \\n');
});

test('Professor timetable search query handles diacritics and regex special characters safely', () => {
  const renderProfessorTimetable = sandbox.renderProfessorTimetable;
  const profState = vm.runInContext('professorScheduleState', context);

  profState.lessons = [
    { id: 'l1', date: '20-10-2026', course: 'Elettrònica dei Sistemi', aula: 'U1-01', docente: 'Prof. Mario Rossi' },
    { id: 'l2', date: '21-10-2026', course: 'Calcolo delle Probabilità', aula: 'U1-02', docente: 'Prof. Mario Rossi' },
    { id: 'l3', date: '22-10-2026', course: 'C++ Special Course [ADV]', aula: 'U1-03', docente: 'Prof. Mario Rossi' }
  ];
  profState.timeScope = 'all';

  const appendedSections = [];
  const mockContainer = {
    innerHTML: '',
    appendChild: (child) => appendedSections.push(child)
  };

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'profUnifiedLessonsContainer') return mockContainer;
    return mockElement();
  };

  try {
    // 1. Accent-insensitive search: 'elettronica' matches 'Elettrònica'
    profState.searchQuery = 'elettronica';
    renderProfessorTimetable();
    assert.strictEqual(appendedSections.length, 1);
    assert.ok(appendedSections[0].innerHTML.includes('1 lezione'));

    // 2. Query with no match: renders empty state
    profState.searchQuery = 'nonexistent_subj_xyz';
    renderProfessorTimetable();
    assert.strictEqual(appendedSections.length, 2);
    assert.strictEqual(appendedSections[1].className, 'empty-state');

    // 3. Regex characters in query: '[ADV]' or 'C++' does not throw regex error
    profState.searchQuery = '[ADV]';
    assert.doesNotThrow(() => renderProfessorTimetable());
    assert.strictEqual(appendedSections.length, 3);
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('Role switching and logout resets timetable view and subtitle cleanly', () => {
  const updateTimetableForRole = sandbox.updateTimetableForRole;
  const handleLogoutProfile = sandbox.handleLogoutProfile;
  const profileState = vm.runInContext('profileState', context);
  const state = vm.runInContext('state', context);
  const profState = vm.runInContext('professorScheduleState', context);

  const mockSubtitle = mockElement();
  const mockProfSection = mockElement();
  const mockStdSection = mockElement();
  const mockBanner = mockElement();
  const mockFilterGroup = mockElement();

  const oldGetEl = sandbox.document.getElementById;
  sandbox.document.getElementById = (id) => {
    if (id === 'headerSubtitle') return mockSubtitle;
    if (id === 'professorTimetableSection') return mockProfSection;
    if (id === 'teachersStandardSearchSection') return mockStdSection;
    if (id === 'profTimetableInfoBanner') return mockBanner;
    if (id === 'timetableFilterToggleGroup') return mockFilterGroup;
    return mockElement();
  };

  try {
    // 1. Professor in timetable tab
    profileState.role = 'professor';
    profileState.nickname = 'Prof. Mario Rossi';
    state.activeTab = 'timetable';
    updateTimetableForRole();

    assert.strictEqual(mockProfSection.style.display, 'block');
    assert.strictEqual(mockBanner.style.display, 'flex');
    assert.strictEqual(mockFilterGroup.style.display, 'none');
    assert.ok(mockSubtitle.textContent.includes('Prof. Mario Rossi'));

    // 2. Professor in teachers tab
    state.activeTab = 'teachers';
    updateTimetableForRole();
    assert.ok(mockSubtitle.textContent.includes('Cattedra docente'));

    // 3. Logout resets to student
    handleLogoutProfile();
    assert.strictEqual(profileState.role, 'student');
    assert.strictEqual(profState.lessons.length, 0);
    assert.strictEqual(mockProfSection.style.display, 'none');
    assert.strictEqual(mockStdSection.style.display, 'block');
    assert.strictEqual(mockBanner.style.display, 'none');
    assert.strictEqual(mockFilterGroup.style.display, 'flex');
  } finally {
    sandbox.document.getElementById = oldGetEl;
  }
});

test('Zero-Leakage local QR code generator creates data URL without calling api.qrserver.com', () => {
  const qrcode = require('../../public/js/qrcode.js');
  assert.strictEqual(typeof qrcode, 'function');
  const qr = qrcode(0, 'M');
  qr.addData('https://orari.didattica.unimib.it/?friend=TEST12');
  qr.make();
  const dataUrl = qr.createDataURL(4, 2);
  assert.ok(dataUrl.startsWith('data:image/gif;base64,'));

  // Verify openShare in appJsCode does NOT contain api.qrserver.com
  assert.strictEqual(appJsCode.includes('api.qrserver.com'), false);
  assert.ok(appJsCode.includes('qr.createDataURL'));
});

test('GDPR Art. 20 export and Art. 17 wipe buttons and transparency elements exist in index.html', () => {
  const htmlPath = path.join(__dirname, '../../public/index.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  assert.ok(html.includes('id="btnExportUserData"'));
  assert.ok(html.includes('id="btnWipeAccount"'));
  assert.ok(html.includes('privacy-details-card'));
  assert.ok(html.includes('Art. 20 Portabilità'));
  assert.ok(html.includes('Art. 17 Diritto all\'Oblio'));
  assert.ok(html.includes('qrcode.js'));
});

test('Service Worker excludes sensitive endpoints from CacheStorage and bundles qrcode.js', () => {
  const swPath = path.join(__dirname, '../../public/sw.js');
  const swCode = fs.readFileSync(swPath, 'utf8');
  assert.ok(swCode.includes('/js/qrcode.js'));
  assert.ok(swCode.includes('SENSITIVE_ENDPOINTS'));
  assert.ok(swCode.includes('/api/profile'));
  assert.ok(swCode.includes('/api/group'));
});

test('Self-hosted fonts are included in Service Worker ASSETS and index.html preloads local WOFF2', () => {
  const swPath = path.join(__dirname, '../../public/sw.js');
  const swCode = fs.readFileSync(swPath, 'utf8');
  assert.ok(swCode.includes('/fonts/pt-sans-v18-latin-regular-400.woff2'));
  assert.ok(swCode.includes('/fonts/pt-sans-narrow-v19-latin-regular-400.woff2'));

  const htmlPath = path.join(__dirname, '../../public/index.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  assert.strictEqual(html.includes('fonts.googleapis.com'), false);
  assert.strictEqual(html.includes('fonts.gstatic.com'), false);
  assert.ok(html.includes('rel="preload" href="/fonts/pt-sans-v18-latin-regular-400.woff2"'));
});

test('Multi-account management and seamless account switching between Student and Professor', async () => {
  const getSavedAccounts = sandbox.getSavedAccounts;
  const saveAccountToStorage = sandbox.saveAccountToStorage;
  const switchAccount = sandbox.switchAccount;
  const removeSavedAccount = sandbox.removeSavedAccount;
  const pState = vm.runInContext('profileState', context);
  const st = vm.runInContext('state', context);

  assert.ok(typeof getSavedAccounts === 'function');
  assert.ok(typeof switchAccount === 'function');

  // 1. Save two accounts (Student and Professor)
  const studentAcc = {
    nickname: 'Mario Studente',
    email: 'm.rossi@campus.unimib.it',
    role: 'student',
    shareCode: 'STUD12',
    sessionToken: 'st_student_token',
    config: { corso: 'F1801Q', corsoLabel: 'Informatica', favorites: [{ code: 'INF1', label: 'Prog' }] }
  };
  const profAcc = {
    nickname: 'Prof. Mario Rossi',
    email: 'mario.rossi@unimib.it',
    role: 'professor',
    shareCode: 'PROF99',
    sessionToken: 'st_prof_token',
    config: null,
    teacherCode: 'T12345'
  };

  saveAccountToStorage(studentAcc);
  saveAccountToStorage(profAcc);

  const saved = getSavedAccounts();
  assert.strictEqual(saved.length >= 2, true);

  // 2. Switch to Student Account
  await switchAccount('m.rossi@campus.unimib.it');
  assert.strictEqual(pState.role, 'student');
  assert.strictEqual(pState.email, 'm.rossi@campus.unimib.it');
  assert.strictEqual(pState.shareCode, 'STUD12');
  assert.strictEqual(st.config && st.config.corso, 'F1801Q');

  // 3. Switch to Professor Account
  await switchAccount('mario.rossi@unimib.it');
  assert.strictEqual(pState.role, 'professor');
  assert.strictEqual(pState.email, 'mario.rossi@unimib.it');
  assert.strictEqual(pState.shareCode, 'PROF99');
  assert.strictEqual(pState.sessionToken, 'st_prof_token');

  // 4. Switch back to Student Account
  await switchAccount('STUD12');
  assert.strictEqual(pState.role, 'student');
  assert.strictEqual(pState.email, 'm.rossi@campus.unimib.it');
  assert.strictEqual(st.config && st.config.corso, 'F1801Q');

  // 5. Remove account test
  removeSavedAccount('STUD12');
  const savedAfterRemove = getSavedAccounts();
  assert.ok(!savedAfterRemove.some(a => a.shareCode === 'STUD12'));
});





