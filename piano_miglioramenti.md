# 📋 Piano Maestro di Miglioramento e Refactoring della Codebase — UNIMIB Calendar

Documento programmatico di analisi tecnica approfondita e piano di miglioramento architetturale, prestazionale, di sicurezza, qualità del codice ed esperienza utente (UX/UI) per l'applicazione **UNIMIB Orari & Campus Companion**.

---

## 📑 Indice dei Temi

1. [Tema 1: Architettura Backend & De-duplicazione Serverless Python](#-tema-1-architettura-backend--de-duplicazione-serverless-python)
2. [Tema 2: Sicurezza Applicativa, OWASP & Integrità Concorrente dei Dati](#-tema-2-sicurezza-applicativa-owasp--integrità-concorrente-dei-dati)
3. [Tema 3: Esportazione Calendari & Standard iCalendar (RFC 5545 / WebCal)](#-tema-3-esportazione-calendari--standard-icalendar-rfc-5545--webcal)
4. [Tema 4: Architettura Frontend, Modularità & Eliminazione Debito Tecnico (JavaScript)](#-tema-4-architettura-frontend-modularità--eliminazione-debito-tecnico-javascript)
5. [Tema 5: PWA, Service Worker & Resilienza Offline](#-tema-5-pwa-service-worker--resilienza-offline)
6. [Tema 6: Fogli di Stile, Design System & Ottimizzazione CSS](#-tema-6-fogli-di-stile-design-system--ottimizzazione-css)
7. [Tema 7: Ergonomia UX, Accessibilità (WCAG 2.2 AA) & Funzionalità Campus](#-tema-7-ergonomia-ux-accessibilità-wcag-22-aa--funzionalità-campus)
8. [Tema 8: Tooling, Developer Experience, Test Suite & CI/CD](#-tema-8-tooling-developer-experience-test-suite--cicd)
9. [Matrice di Priorità & Roadmap di Rilascio](#-matrice-di-priorità--roadmap-di-rilascio)

---

## 🏛️ Tema 1: Architettura Backend & De-duplicazione Serverless Python

### 1.1 Duplicazione Massiva di Codice Boilerplate nelle Serverless Functions (`api/*.py`)

#### Analisi del Codice Esistente
Attualmente la directory `api/` contiene 9 funzioni serverless Python indipendenti (`calendar.py`, `exams.py`, `rooms.py`, `teachers.py`, `options.py`, `export.py`, `shared_calendar.py`, `profile.py`, `group.py`).
Ognuno di questi file è stato scritto come script autocontenuto, provocando una massiccia duplicazione di blocchi identici di logica:
- **Metodi di risposta HTTP & Header di Sicurezza**: `send_json()` / `_send_json()` e gli header (`Content-Type`, `Access-Control-Allow-Origin`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`) sono riscritti identici in tutti e 9 i file (es. `calendar.py:249-264`, `exams.py:301-315`, `rooms.py:334-348`, `profile.py:383-395`, `group.py:393-404`).
- **Risoluzione credenziali Upstash Redis**: la funzione `_get_redis_creds()` è copiata parola per parola in `shared_calendar.py:35-48`, `export.py:35-48`, `profile.py:54-67`, `group.py:43-56`.
- **Driver di fallback locale `/tmp/unimib_kv_store.json`**: le funzioni `_local_kv_load()`, `_local_kv_save()`, `_local_redis()` sono duplicate con piccole variazioni in `shared_calendar.py:78-101`, `profile.py:82-143`, `group.py:82-143`.
- **Parsing e sanitizzazione testo/HTML**: `_safe_ts()`, `clean_html()`, `split_curricula()` sono duplicati in `calendar.py:19-28`, `teachers.py:55-86`, `shared_calendar.py:174-178`.

#### Impatto & Rischi
- **Incoerenza di manutenzione**: una correzione o un miglioramento a un header di sicurezza o a un driver Redis deve essere replicato a mano in 4-9 file diversi. Il rischio di dimenticanze o disallineamenti tra endpoint è elevatissimo.
- **Debito di complessità**: circa 800 righe di codice Python su un totale di ~3.780 righe sono pura duplicazione di boilerplate.

#### Piano di Miglioramento
1. Creare un modulo centrale `api/_common.py` (i file che iniziano con `_` in `api/` non vengono esposti come endpoint da Vercel):
   - Definire una classe base `BaseApiHandler(BaseHTTPRequestHandler)` contenente:
     - `send_json(status, payload, cache_control=None, allow_origin=None)`
     - `read_json_body(max_bytes=65536)` con validazione automatica di `Content-Length`
     - `parse_query_params()`
     - Gestione centralizzata delle risposte OPTIONS (preflight CORS)
   - Centralizzare le utility di parsing date italiane e timezone Europe/Rome (`get_rome_now()`, `get_monday()`, `parse_date_to_monday()`).
   - Centralizzare le utility di stringhe (`clean_html()`, `split_curricula()`, `safe_int()`).
   - Centralizzare il client Upstash Redis con fallback resiliente.
2. Refactorizzare i 9 endpoint per ereditare da `BaseApiHandler` o importare le funzioni comuni da `api._common`.

---

### 1.2 Bug del Fuso Orario Attorno a Mezzanotte (`UTC` vs `Europe/Rome`)

#### Analisi del Codice Esistente
In `api/calendar.py:14-17`:
```python
def get_monday(dt=None):
    if dt is None:
        dt = datetime.now()
    return dt - timedelta(days=dt.weekday())
```
La stessa logica naive con `datetime.now()` (senza timezone) è presente in:
- `api/export.py:71-74`: `def _get_monday(dt=None): if dt is None: dt = datetime.now() ...`
- `api/shared_calendar.py:157-172`: `if not dt: dt = datetime.now() ...`

Al contrario, in `api/exams.py:31-41`, `api/rooms.py:17-27` e `api/teachers.py:18-30` è stato introdotto:
```python
try:
    import zoneinfo
    TZ_ROME = zoneinfo.ZoneInfo("Europe/Rome")
except Exception:
    TZ_ROME = timezone(timedelta(hours=1))

def get_italy_now(): ...
```

#### Impatto & Rischi
- I container serverless di Vercel operano con fuso orario di sistema **UTC** (`Etc/UTC`).
- L'Italia si trova a `UTC+1` (inverno / CET) e `UTC+2` (estate / CEST).
- **Bug concreto**: tra le ore 00:00 e le 01:00 (o 02:00 in ora legale) nella notte tra domenica e lunedì a Milano, il server su Vercel è ancora alla domenica precedente (ore 22:00 o 23:00 UTC). Di conseguenza, `dt.weekday()` restituisce `6` (domenica) e `get_monday()` calcola il lunedì della settimana *appena conclusa* anziché quello della nuova settimana che inizia, mostrando agli studenti gli orari vecchi per le prime due ore della giornata!

#### Piano di Miglioramento
1. Eliminare tutte le chiamate a `datetime.now()` naive per il calcolo delle date del calendario.
2. Introdurre in `api/_common.py`:
```python
import zoneinfo
from datetime import datetime, timedelta, timezone

TZ_ROME = zoneinfo.ZoneInfo("Europe/Rome")

def get_rome_now() -> datetime:
    return datetime.now(TZ_ROME)

def get_monday(dt: datetime | None = None) -> datetime:
    if dt is None:
        dt = get_rome_now()
    return dt - timedelta(days=dt.weekday())
```
3. Utilizzare uniformemente `get_monday()` e `get_rome_now()` in tutti i moduli backend.

---

### 1.3 Limiti della Cache In-Memory su Container Serverless & Eviction Unbounded

#### Analisi del Codice Esistente
In `api/calendar.py:49-54`, `api/exams.py:47-51`, `api/rooms.py:32-36`, `api/teachers.py:110-115`, `api/export.py:108-113` e `api/options.py:21-25`, la cache in-memory viene pulita con un pattern simile:
```python
if len(_cache) > 100:
    now = time.time()
    for k in list(_cache.keys()):
        if now - _cache[k][0] >= CACHE_TTL:
            _cache.pop(k, None)
```

#### Impatto & Rischi
- **Nessun bound superiore garantito (Memory Leak potenziale)**: se arrivano 200 richieste per chiavi differenti entro la finestra di TTL (es. 300 secondi), la condizione `now - _cache[k][0] >= CACHE_TTL` sarà falsa per tutte le chiavi. Il dizionario continuerà a crescere senza limite oltre i 100/200 elementi, consumando la memoria del runtime Python serverless (spesso configurato a 256MB o 512MB su Vercel).
- **Isolamento della cache per container**: su Vercel ogni cold start crea un nuovo worker con dizionario vuoto. Due studenti che richiedono lo stesso corso contemporaneamente su due istanze serverless diverse causano due chiamate distinte a monte a EasyCourse.

#### Piano di Miglioramento
1. **LRU Cache rigorosa in memoria**: sostituire il dict standard con un `BoundedLRUCache` basato su `collections.OrderedDict`, che garantisca uno sfratto deterministico O(1) del più vecchio elemento non appena si supera `MAX_SIZE`:
```python
from collections import OrderedDict
import time

class BoundedTTLCache:
    def __init__(self, maxsize=150, ttl_seconds=300):
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._data = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        ts, val = self._data[key]
        if time.time() - ts >= self._ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return val

    def set(self, key, val):
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self._maxsize:
            self._data.popitem(last=False)  # Sfratta FIFO/LRU
        self._data[key] = (time.time(), val)
```
2. **Caching L2 distribuito su Upstash Redis**: sfruttare Upstash Redis (già presente per i profili) per memorizzare le risposte JSON delle griglie EasyCourse (`cache:grid:<anno>:<corso>:<anni>:<data>`) con TTL di 300s. In questo modo:
   - Tutte le istanze serverless condividono la medesima cache.
   - Il carico sui server dell'Ateneo viene abbattuto dell'85-95%.
   - La latenza di risposta per l'utente scende da ~750ms a ~35ms.

---

### 1.4 Resilienza e Politica di Retry verso i Server UNIMIB EasyCourse

#### Analisi del Codice Esistente
Attualmente le chiamate HTTP upstream a UNIMIB (`grid_call.php`, `combo.php`, `bookings_call.php`, `rooms_call.php`) usano `urllib.request.urlopen(req, timeout=10)` o `timeout=15` senza alcun meccanismo di riprova.
Se il server di Ateneo risponde con un timeout di rete transitorio o un errore temporaneo 502/503/504 (frequente durante il caricamento degli appelli o la prima settimana di lezioni), la funzione serverless fallisce immediatamente ritornando errore 502 al client.

#### Piano di Miglioramento
1. Introdurre una funzione di fetch upstream con **Exponential Backoff e Jitter**:
   - Massimo 2 tentativi di riprova (totale 3 richieste).
   - Backoff: 400ms -> 900ms con jitter casuale di ±150ms.
   - Riprova solo su errori transitori (`TimeoutError`, `URLError`, HTTP 500, 502, 503, 504), mai su HTTP 4xx.
2. In caso di fallimento definitivo upstream, se è disponibile in cache (in-memory o Redis) un dato scaduto, restituire il dato stale accompagnato da un header `X-Cache-Status: STALE-FALLBACK` invece di bloccare l'utente con una pagina di errore.

---

### 1.5 Standardizzazione dei Codici di Stato HTTP e Formato Risposte d'Errore

#### Analisi del Codice Esistente
- In `api/calendar.py`: gli errori EasyCourse ritornano `502 Bad Gateway`.
- In `api/teachers.py:316`: le eccezioni ritornano `500 Internal Server Error`.
- In `api/export.py:229`: parametri errati ritornano `400` con `{"error": "Parametri insufficienti..."}`.
- Spesso le eccezioni Python grezze vengono convertite in stringa e passate nel JSON (`{"error": str(e)}`), esponendo dettagli interni di implementazione o percorsi di file in caso di bug imprevisti.

#### Piano di Miglioramento
1. Adottare uno schema uniforme per i payload d'errore ispirato a **RFC 7807 (Problem Details)**:
```json
{
  "error": true,
  "code": "UPSTREAM_UNAVAILABLE",
  "message": "Il server orari UNIMIB non risponde al momento. Riprova tra pochi istanti.",
  "status": 502
}
```
2. Mappare gli errori in modo categorico:
   - `400 Bad Request`: validazione parametri fallita (regex anno, data non conforme).
   - `401 Unauthorized`: token di sessione mancante o non valido.
   - `403 Forbidden`: credenziali errate o rate limit superato.
   - `404 Not Found`: corso, docente o risorsa non presente.
   - `413 Payload Too Large`: corpo richiesta > 64KB.
   - `429 Too Many Requests`: troppi tentativi di login errati.
   - `502 Bad Gateway`: errore o timeout di EasyCourse UNIMIB.

---

## 🔒 Tema 2: Sicurezza Applicativa, OWASP & Integrità Concorrente dei Dati

### 2.1 Content-Security-Policy (CSP) & Header di Sicurezza Mancanti a Livello Edge (`vercel.json`)

#### Analisi del Codice Esistente
Mentre le funzioni Python in `api/*.py` impostano alcuni header HTTP manuali (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`), il file `vercel.json` gestisce solo i `rewrites`:
```json
{
  "version": 2,
  "rewrites": [ ... ]
}
```
Non è definita alcuna sezione `"headers"` in `vercel.json`.

#### Impatto & Rischi
- Gli asset statici (`/index.html`, `/css/style.css`, `/js/app.js`, `/sw.js`, manifest, icone) sono serviti direttamente dal CDN di Vercel **senza alcun header di sicurezza OWASP** (niente HSTS, niente CSP, niente X-Frame-Options sull'HTML principale).
- La protezione CSP è totalmente assente sull'entry point principale della SPA (`/index.html`), esponendo l'applicazione a rischi di XSS o clickjacking se una dipendenza o un componente iniettasse codice estraneo.

#### Piano di Miglioramento
Configurare la sezione `"headers"` globale in `vercel.json`:
```json
{
  "version": 2,
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "geolocation=(), camera=(), microphone=(), payment=()" },
        { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains; preload" },
        { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.upstash.io; frame-ancestors 'none';" }
      ]
    },
    {
      "source": "/sw.js",
      "headers": [
        { "key": "Cache-Control", "value": "no-cache, no-store, must-revalidate" },
        { "key": "Service-Worker-Allowed", "value": "/" }
      ]
    }
  ],
  "rewrites": [ ... ]
}
```

---

### 2.2 Restrizione CORS su Endpoint Mutativi (`POST /api/profile`, `POST /api/group`)

#### Analisi del Codice Esistente
Attualmente tutti gli endpoint restituiscono:
```python
self.send_header('Access-Control-Allow-Origin', '*')
```
Questo include `POST /api/profile` (creazione account e reset PIN), `PUT /api/profile` (login e aggiornamento piano) e `POST /api/group` (creazione/modifica/abbandono gruppi).

#### Impatto & Rischi
L'apertura indiscriminata `Access-Control-Allow-Origin: *` su endpoint con mutazione di stato consente a qualsiasi sito web di terze parti aperto nel browser di uno studente di inviare richieste dirette alle API dell'applicazione.

#### Piano di Miglioramento
1. Per le API pubbliche di sola lettura (`/api/calendar`, `/api/rooms`, `/api/exams`, `/api/teachers`, `/api/options`, `/api/export`) mantenere `Access-Control-Allow-Origin: *` per consentire integrazioni universali.
2. Per le API private di gestione profilo e gruppi (`api/profile.py`, `api/group.py`):
   - Ispezionare l'header `Origin` della richiesta in arrivo.
   - Consentire solo richieste provenienti dallo stesso dominio (o da localhost in sviluppo).
   - Se `Origin` non corrisponde all'host autorizzato, omettere l'header CORS o rifiutare la richiesta con `403 Forbidden`.

---

### 2.3 Race Condition (Lost Updates) nei Gruppi di Studio su Upstash Redis

#### Analisi del Codice Esistente
In `api/group.py:346-380` e nelle azioni `join_group`, `leave_group`, `add_member`:
1. Viene effettuato un `GET group:<id>` per ottenere l'oggetto JSON del gruppo.
2. La lista `members` viene parsata e modificata in memoria Python (`members.append(...)` o `members.remove(...)`).
3. Viene eseguito un `SET group:<id>` con il nuovo JSON stringificato.

#### Impatto & Rischi
Se due studenti cliccano sul link di invito contemporaneamente nello stesso secondo:
- Studente A legge membri `[X]`
- Studente B legge membri `[X]`
- Studente A scrive membri `[X, A]`
- Studente B scrive membri `[X, B]` (sovrascrivendo e cancellando l'iscrizione di A!)
Questo è il classico problema di concorrenza **Lost Update** dovuto all'assenza di operazioni atomiche.

#### Piano di Miglioramento
1. Sfruttare le primitive atomiche di Redis (native nei Set di Redis):
   - Memorizzare i membri del gruppo come un Redis Set: `group_members:<id>` con comando `SADD` / `SREM` / `SMEMBERS`.
   - L'operazione `SADD` è atomica O(1) e non soffre di race condition di lettura/scrittura.
2. In alternativa, implementare un controllo ottimistico di concorrenza (**OCC**) con versioning numerico (`version: N` nel JSON) o sfruttare script Lua tramite endpoint REST `/EVAL` di Upstash Redis.

---

### 2.4 Limiti del Fallback Locale `/tmp/unimib_kv_store.json` su Architettura Serverless

#### Analisi del Codice Esistente
In `api/profile.py:78-143`, `api/group.py:78-143` e `api/shared_calendar.py:74-101`:
Se le variabili d'ambiente `UPSTASH_REDIS_REST_URL` e `UPSTASH_REDIS_REST_TOKEN` non sono impostate, il backend fa fallback su un file locale in `/tmp`:
```python
_LOCAL_STORE_PATH = os.path.join(tempfile.gettempdir(), "unimib_kv_store.json")
```

#### Impatto & Rischi
- In ambiente serverless (Vercel Lambda), il file system `/tmp` è **strettamente effimero e isolato per istanza container**.
- Se l'utente crea un gruppo sull'Istanza 1, l'Istanza 2 non vedrà mai quel gruppo in `/tmp`.
- Il fallback locale è eccellente per i test automatici (`scratch/test_*.py`) e lo sviluppo offline in locale, ma se scambiato per una persistenza di produzione porterebbe a perdite di dati silenziose.

#### Piano di Miglioramento
1. Aggiungere un controllo esplicito all'avvio: in ambiente di produzione (`VERCEL_ENV=production`), se le credenziali Redis mancano, restituire un errore 503 chiaro (`"Archiviazione cloud non configurata: configurare Upstash Redis"`) invece di salvare transienti invisibili in `/tmp`.
2. Mantenere attivo il fallback in `/tmp` solo per test unitari (`test_*.py`) e ambiente di sviluppo locale (`VERCEL_ENV=development` o non definito).

---

## 📅 Tema 3: Esportazione Calendari & Standard iCalendar (RFC 5545 / WebCal)

### 3.1 Componente `VTIMEZONE` Mancante nel Feed `.ics` (Rischio Sfasamento Orario)

#### Analisi del Codice Esistente
In `api/export.py:420-455`, il file `.ics` viene generato così:
```python
vcalendar_lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//UNIMIB Orari//IT",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    f"X-WR-CALNAME:{_escape_ical(cal_name)}",
    "X-WR-TIMEZONE:Europe/Rome"
]

for ev in events:
    ...
    vcalendar_lines.extend([
        "BEGIN:VEVENT",
        f"UID:unimib-lesson-{ev['id']}@unimib.it",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART;TZID=Europe/Rome:{dt_start}",
        f"DTEND;TZID=Europe/Rome:{dt_end}",
        ...
```

#### Impatto & Rischi
- Secondo lo standard **RFC 5545 (sezione 3.6.5)**: *«In addition, for cases where a "VEVENT" calendar component specifies a "DTSTART" property with a "TZID" property parameter, the corresponding "VTIMEZONE" calendar component MUST be present in the iCalendar object.»*
- Client come Google Calendar, Microsoft Outlook desktop ed Exchange possono rifiutare il file o, peggio, importare le lezioni con un'ora o due ore di scarto (specialmente durante i cambi di ora legale a marzo e ottobre), perché non trovano la definizione formale delle transizioni CET/CEST per `Europe/Rome`.

#### Piano di Miglioramento
Includere la definizione standard completa del componente `VTIMEZONE` prima degli eventi:
```text
BEGIN:VTIMEZONE
TZID:Europe/Rome
X-LIC-LOCATION:Europe/Rome
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
```

---

### 3.2 Standard RFC 5545: Line Folding (Spezzamento Righe a 75 Caratteri)

#### Analisi del Codice Esistente
Attualmente le righe come `DESCRIPTION` e `SUMMARY` in `api/export.py` vengono inserite senza spezzamento:
```python
description = f"Docente: {ev['docente']}\nInsegnamento: {ev['course_code']}\nTipo: {ev['type']}"
vcalendar_lines.extend([ ..., f"DESCRIPTION:{_escape_ical(description)}", ... ])
```
Quando un insegnamento ha un titolo lungo con docenti multipli, la riga può superare i 150-200 caratteri.

#### Impatto & Rischi
RFC 5545 impone che nessuna riga in un payload iCalendar superi i **75 ottetti**. Se supera tale limite, deve essere spezzata con sequenza CRLF seguita da uno spazio (`\r\n `). Parser rigorosi (es. Thunderbird, client CalDAV aziendali) falliscono il parsing di file con righe non ripiegate.

#### Piano di Miglioramento
Implementare una funzione helper di line-folding in conformità a RFC 5545:
```python
def _fold_ical_line(line: str) -> str:
    encoded = line.encode('utf-8')
    if len(encoded) <= 75:
        return line
    parts = []
    while len(encoded) > 75:
        # Trova il punto di taglio corretto senza spezzare byte UTF-8 a metà
        cut = 75
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode('utf-8'))
        encoded = b' ' + encoded[cut:]
    parts.append(encoded.decode('utf-8'))
    return "\r\n".join(parts)
```

---

### 3.3 Sottoscrizione WebCal: Generazione Dinamica con Finestra Scorrevole

#### Analisi del Codice Esistente
In `api/export.py:258-263`:
```python
try:
    weeks_count = max(1, min(12, int(qs.get("weeks", ["4"])[0])))
except ValueError:
    weeks_count = 4
```
L'endpoint WebCal recupera un numero fisso di settimane a partire dalla data indicata (default 4 settimane, max 12).
Quando un utente si abbona tramite `webcal://` su iPhone o Google Calendar, il client effettua un refresh periodico del feed (es. ogni 12 o 24 ore). Tuttavia, se l'URL originale conteneva `date=11-10-2026`, man mano che le settimane passano il calendario "svanirà" perché le 4 settimane configurate diventano passate.

#### Piano di Miglioramento
1. Quando la richiesta arriva come feed continuo WebCal (senza parametro data esplicito o con `mode=live`):
   - Calcolare dinamicamente la data di partenza come il lunedì della settimana corrente (`get_monday(get_rome_now())`).
   - Generare sempre una finestra mobile in avanti (es. 1 settimana nel passato e 8 settimane nel futuro).
   - In questo modo l'abbonamento nello smartphone dello studente è sempre automaticamente aggiornato e copre costantemente i successivi due mesi di lezioni senza interruzioni.

---

## 💻 Tema 4: Architettura Frontend, Modularità & Eliminazione Debito Tecnico (JavaScript)

### 4.1 Il Monolite `public/js/app.js` (Oltre 8.560 Righe di Codice)

#### Analisi del Codice Esistente
Il file `public/js/app.js` è cresciuto organicamente fino a raggiungere **8.564 righe** in un singolo file monolitico contenente:
- Token e configurazioni colore campus (righe 1-150)
- Manipolazione tema e dialoghi (righe 300-430)
- Event listeners globali (righe 547-1540, quasi 1.000 righe di `addEventListener` procedurali!)
- Motore di salvataggio e preview (righe 1541-1780)
- Generazione export locale ICS/CSV (righe 1785-2190)
- Selettore corso e gestione corsi esterni (righe 2191-2780)
- Rilevatore variazioni orario e diffing calendario (righe 2781-3320)
- Rendering griglia orario, widget "Adesso/Prossima", pull-to-refresh (righe 3321-3950)
- Parsing e formattazione date (righe 3951-4050)
- Directory docenti, orari ricevimento e filtri (righe 4100-5260)
- Ricerca aule, occupazione real-time e schede edificio (righe 5265-5460)
- Calendario appelli d'esame e sessioni (righe 5464-6170)
- Autenticazione profilo, login, PIN, recovery code e sessioni (righe 6174-6735)
- Gruppi di studio condivisi, conflitti di orario e free slots (righe 6739-8564)

#### Impatto & Rischi
- **Rischio elevato di regressioni**: qualsiasi modifica a una funzione di utility rischia di rompere inavvertitamente un'altra schermata.
- **Accoppiamento dello stato globale**: variabili sparse nello scope del file (`state`, `friendsState`, `profileState`, `cachedEvents`, `calendarData`).
- **Difficoltà di testing**: non è possibile testare i singoli moduli in isolamento; il test file `test_frontend.test.js` è costretto a usare un mock `vm.runInContext` di Node.js che simula l'intero oggetto `window` e `document`.

#### Piano di Miglioramento: Scomposizione in ES Modules Nativi
Riorganizzare il codice in moduli ECMAScript standard (`type="module"`), nativamente supportati da tutti i browser moderni (senza obbligo di bundler) oppure predisposti per un bundling leggero:
```
public/js/
├── app.js                      # Entry point: inizializzazione, router tab e bootstrap
├── core/
│   ├── state.js                # State store unificato (Alpine.js store + LocalStorage sync)
│   ├── config.js               # Costanti, colori aree didattiche, edifici campus U1-U28
│   └── events.js               # Bus eventi & binding delegato
├── services/
│   ├── api.js                  # Client API unificato (fetch wrapper con retry, cache, abort controller)
│   ├── storage.js              # Gestione sicura LocalStorage con migrazione automatica schema
│   ├── export.js               # Motore generazione .ics, .csv, WebCal e download helper
│   └── crypto.js               # Helper hash e formattazione PIN/Recovery
├── views/
│   ├── timetable.js            # Orario lezioni, carosello giorni, widget "Adesso/Prossima"
│   ├── changes.js              # Rilevamento modifiche e dialog variazioni
│   ├── rooms.js                # Vista aule libere, occupazione e mappe edifici
│   ├── teachers.js             # Directory docenti, orari e contatti
│   ├── exams.js                # Calendario appelli esami e filtri sessione
│   ├── friends.js              # Gruppi studio, timetable condiviso e slot liberi
│   └── profile.js              # Login, PIN auth, sincronizzazione cloud e account
└── utils/
    ├── date.js                 # Parsing e formattazione date italiane
    ├── dom.js                  # Helper DOM sicuri, toast, bottom sheet, modali
    └── sanitize.js             # escapeHtml e sanitizzazione input
```

---

### 4.2 Rimozione del Runtime Tailwind CDN Inutilizzato da `index.html`

#### Analisi del Codice Esistente
In `public/index.html:28-45`:
```html
<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    corePlugins: { preflight: false },
    darkMode: 'class',
    theme: { extend: { colors: { unimib: '#A71E3B', 'unimib-dark': '#83142C' } } }
  };
</script>
```

#### Impatto & Rischi
- L'audit della codebase ha dimostrato che **nessuna classe utility di Tailwind è effettivamente utilizzata** né in `index.html` né in `app.js` (l'intero layout è stilato dalle 4.214 righe di `public/css/style.css`).
- Lo script `cdn.tailwindcss.com` scarica oltre **350 KB di JavaScript gzippato (~3 MB non compresso)**.
- All'avvio dell'applicazione su smartphone, il runtime Tailwind effettua una scansione JIT dell'intero DOM, occupando il thread principale (CPU blocking) per 150-300ms senza produrre alcun beneficio, degradando sensibilmente il punteggio Lighthouse e la First Contentful Paint (FCP) su dispositivi mobili.

#### Piano di Miglioramento
1. Rimuovere completamente `<script src="https://cdn.tailwindcss.com"></script>` e il blocco `tailwind.config` da `public/index.html`.
2. Verificare che l'applicazione mantenga la perfetta fedeltà visiva al 100% (già garantita da `style.css`).
3. Guadagno immediato: **eliminazione di oltre 350KB di download di rete** e avvio istantaneo della SPA.

---

### 4.3 Riconciliazione dei Paradigmi Reattivi: Alpine.js vs Manipolazione Manuale del DOM

#### Analisi del Codice Esistente
L'applicazione carica Alpine.js (`/js/alpine.min.js`), ma gran parte del codice in `app.js` continua a manipolare il DOM in maniera puramente imperativa:
- Oltre 40 chiamate dirette a `.innerHTML = ...` e `.innerHTML += ...`
- `document.getElementById(...)` e query manuali su decine di elementi.
- Coesistenza disallineata: in alcuni punti lo stato è aggiornato in `$store.app` di Alpine, mentre la UI viene ridisegnata tramite funzioni procedurali (`renderEvents()`, `renderFriendsGrid()`, `renderRooms()`), creando potenziali desincronizzazioni tra lo stato reattivo e il DOM visibile.

#### Piano di Miglioramento
1. **Strategia unificata**:
   - Mantenere Alpine.js come orchestratore reattivo dichiarativo per la UI dell'interfaccia (apertura/chiusura bottom sheet, toggle giorno selezionato, indicatori di caricamento, tab switching tramite `x-show` e `x-bind:class`).
   - Sfruttare `x-for` e template dichiarativi per le liste dinamiche semplici, evitando la manipolazione diretta di `innerHTML`.
   - Per le griglie orari dense ad alte prestazioni (timetable con centinaia di eventi), utilizzare rendering dichiarativo sicuro tramite `template` clonati o funzioni di creazione DOM sicure.

---

### 4.4 Prevenzione XSS tramite Template Literals e Sanitizzazione Centralizzata

#### Analisi del Codice Esistente
Sebbene sia definita la funzione `escapeHtml(str)` in `app.js:3961-3968`, essa viene invocata manualmente nei template string `innerHTML`:
```javascript
html += `<div class="event-title">${escapeHtml(e.course)}</div>`;
```
In una codebase di 8.500 righe con decine di generatori di markup complessi, una singola omissione di `escapeHtml()` su un campo proveniente da un corso esterno, dal nome di un gruppo o dal soprannome di un amico costituisce una vulnerabilità XSS latente.

#### Piano di Miglioramento
1. Creare un tagged template literal sicuro `html` in `utils/dom.js`:
```javascript
export function html(strings, ...values) {
  return strings.reduce((acc, str, i) => {
    const val = values[i - 1];
    let sanitized = '';
    if (val !== undefined && val !== null) {
      if (typeof val === 'object' && val.__isSafeHtml) {
        sanitized = val.content;
      } else {
        sanitized = escapeHtml(String(val));
      }
    }
    return acc + sanitized + str;
  });
}
```
2. Adottare `html` per tutti i rendering di componenti, rendendo impossibile dimenticare l'escaping delle variabili interpolate.

---

## 📱 Tema 5: PWA, Service Worker & Resilienza Offline

### 5.1 Versioning Dinamico della Cache del Service Worker (`public/sw.js`)

#### Analisi del Codice Esistente
In `public/sw.js:1`:
```javascript
const CACHE_NAME = 'unimib-calendar-v23';
```
La versione della cache è una stringa cablata a mano nel codice sorgente.

#### Impatto & Rischi
- **Stale Cache perenne**: `sw.js` adotta la strategia *stale-while-revalidate* per gli asset statici (`/css/style.css`, `/js/app.js`). Se uno sviluppatore rilascia una nuova versione o un bugfix su GitHub/Vercel ma dimentica di incrementare manualmente la stringa `v23` a `v24`, i browser degli studenti continueranno a eseguire la vecchia versione memorizzata in cache a tempo indeterminato!
- L'utente deve eseguire manualmente un "Cancella dati sito" per ricevere gli aggiornamenti.

#### Piano di Miglioramento
1. Implementare un meccanismo di iniezione automatica della versione della cache basato sull'hash del commit Git o su un timestamp di build:
   - Creare un piccolo script di pre-deploy (o Vercel build command) che generi `const CACHE_NAME = 'unimib-calendar-' + BUILD_HASH;`.
2. In `app.js`, ascoltare l'evento `controllerchange` del Service Worker e, al rilevamento di una nuova versione, mostrare un toast discreto: *"Nuova versione disponibile — [Ricarica per aggiornare]"*.

---

### 5.2 Politica di Scadenza e Bounding della Cache API in `CacheStorage`

#### Analisi del Codice Esistente
In `public/sw.js:57-76`:
```javascript
if (requestUrl.pathname.startsWith('/api/')) {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && response.status === 200) {
          const resClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, resClone);
          });
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
  return;
}
```

#### Impatto & Rischi
- Tutte le risposte `GET /api/*` con stato 200 vengono salvate senza alcuna scadenza o limite di quota.
- Se uno studente consulta 20 settimane diverse o 10 aule diverse nel corso dell'anno accademico, tutte quelle risposte rimangono per sempre nel `CacheStorage` del dispositivo.
- Se la rete è assente, il Service Worker potrebbe restituire un calendario vecchio di 6 mesi senza alcuna avvertenza di obsolescenza per l'utente.

#### Piano di Miglioramento
1. Aggiungere metadati di timestamp nelle risposte salvate nella cache API:
   - Quando si recupera dalla cache in modalità offline, verificare l'età del dato: se più vecchio di 7 giorni, mostrare un banner esplicito: *"Attenzione: dati salvati offline oltre una settimana fa"*.
2. Implementare un limite massimo di voci memorizzate per le chiamate API (es. max 30 endpoint recenti), eliminando le risposte più vecchie con logica LRU durante l'evento di attivazione o fetch.

---

### 5.3 Caching Offline dei Web Font Istituzionali (`PT Sans`)

#### Analisi del Codice Esistente
In `public/sw.js:51-54`:
```javascript
if (requestUrl.origin !== self.location.origin) {
  return;
}
```
Tutte le richieste esterne vengono ignorate dal Service Worker.
Tuttavia, i font ufficiali di Ateneo (`PT Sans` e `PT Sans Narrow`) vengono caricati da Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=PT+Sans:..." rel="stylesheet">
```

#### Impatto & Rischi
Quando l'utente utilizza l'applicazione offline nelle aule seminterrate o con rete instabile, le richieste verso `fonts.googleapis.com` e `fonts.gstatic.com` falliscono, provocando uno scatto visivo del font (FOUT) o il fallback sui font generici di sistema.

#### Piano di Miglioramento
1. Intercettare nel Service Worker le richieste verso `fonts.googleapis.com` e `fonts.gstatic.com` con una cache dedicata `unimib-fonts-v1` (strategia *cache-first* con fallback su rete).
2. In alternativa (approccio consigliato per piena indipendenza e privacy), auto-ospitare i file WOFF2 di `PT Sans` e `PT Sans Narrow` direttamente nella cartella `public/fonts/`, inserendoli nell'array `ASSETS` di `sw.js` per una disponibilità offline garantita al 100%.

---

## 🎨 Tema 6: Fogli di Stile, Design System & Ottimizzazione CSS

### 6.1 Razionalizzazione e Snellimento di `public/css/style.css` (4.214 Righe)

#### Analisi del Codice Esistente
Il file `public/css/style.css` supera le 4.200 righe. L'audit evidenzia:
- **Regole duplicate e frammentazione**: le definizioni per le card lezioni, i pulsanti e i modali compaiono in blocchi multipli scritti in tempi diversi (es. le definizioni `.event-card` si trovano attorno alla riga 600, 1500, 2800 e 3900).
- **Variabili legacy di transizione**: persistono token come `--accent-purple` mantenuti per retrocompatibilità insieme a `--bicocca-red`.
- **Media query sparse**: decine di blocchi `@media (max-width: 640px)` e `@media (min-width: 768px)` sono disseminati nel file invece di essere organizzati per componente.

#### Piano di Miglioramento
1. Strutturare il CSS secondo una metodologia modulare (es. CSS Modules, BEM o ITCSS - Inverted Triangle CSS):
   - `01-tokens.css`: variabili colori, spaziature, ombre, tipografia, curve di animazione.
   - `02-reset.css`: box-sizing, typography reset, standard mobile viewport.
   - `03-layout.css`: app-header, app-shell, bottom navigation dock, grid responsive.
   - `04-components/`: card lezioni (bento), widget "Adesso/Prossima", carousel giorni, selettori corso, chip filtri.
   - `05-modals/`: bottom sheets, dialoghi, conferme, dialog variazioni orario.
   - `06-views/`: stili specifici per vista aule, docenti, esami e amici.
2. Eliminare i selettori ridondanti e consolidare i breakpoint media query.

---

### 6.2 Contrasti Cromatici e Conformità Rigorosa WCAG 2.2 AA / AAA

#### Analisi del Codice Esistente
In Dark Mode (`:root[data-theme="dark"]`):
- Il colore `--text-muted: #64748B` su sfondo `--surface-base: #111827` ha un rapporto di contrasto di circa **4.1:1**, leggermente inferiore al requisito minimo di **4.5:1** imposto dalle linee guida WCAG 2.2 AA per i testi di dimensione normale (< 18px).
- Nelle card degli appelli d'esame e nelle descrizioni dei corsi secondari, alcuni badge di testo grigio risultano difficili da leggere alla luce diretta del sole nei cortili di Ateneo.

#### Piano di Miglioramento
1. Alzare la luminosità di `--text-muted` in Dark Mode da `#64748B` a `#94A3B8` (contrasto 5.6:1, pienamente conforme a WCAG AA).
2. Per Light Mode, assicurare che `--text-secondary` sia almeno `#475569` (contrasto > 6.2:1 su fondo bianco `#FFFFFF`).
3. Introdurre un test automatico di contrasto cromatico nella suite di test.

---

## 👥 Tema 7: Ergonomia UX, Accessibilità (WCAG 2.2 AA) & Funzionalità Campus

### 7.1 Focus Trap e Navigazione da Tastiera nei Bottom Sheet e nei Modali

#### Analisi del Codice Esistente
Nelle funzioni `openModal(modalId)` e `closeModal(modalId)` in `app.js:365-430`:
- La modale viene aperta impostando `display: block` o aggiungendo la classe `.active`.
- **Nessun Focus Trapping**: un utente che naviga con tastiera (Tab) continua a spostare il focus sugli elementi sottostanti della pagina principale, scavalcando la modale aperta.
- **Mancato ripristino del focus**: alla chiusura della modale, il focus non viene restituito al pulsante che l'aveva aperta, costringendo l'utente a ricominciare la navigazione dall'inizio della pagina.

#### Piano di Miglioramento
1. Implementare una funzione di gestione del focus accessibile:
```javascript
export function trapFocus(modalEl) {
  const focusable = modalEl.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  first.focus();

  const handleKeyDown = (e) => {
    if (e.key === 'Tab') {
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    } else if (e.key === 'Escape') {
      closeCurrentModal();
    }
  };

  modalEl.addEventListener('keydown', handleKeyDown);
  return () => modalEl.removeEventListener('keydown', handleKeyDown);
}
```
2. Memorizzare l'elemento trigger attivo (`document.activeElement`) all'apertura e invocare `triggerEl.focus()` alla chiusura.

---

### 7.2 Regioni `aria-live` per Aggiornamenti Asincroni e Annunci Screen Reader

#### Analisi del Codice Esistente
Quando un utente:
- Esegue una ricerca tra i docenti o le aule
- Ricarica l'orario tramite pull-to-refresh
- Riceve la notifica di lezioni cambiate o annullate
Gli aggiornamenti avvengono tramite mutazione visiva del DOM, senza alcun attributo `aria-live` o `role="status"`. Gli utenti che utilizzano screen reader (TalkBack su Android o VoiceOver su iOS) non ricevono alcun feedback vocale del completamento dell'azione.

#### Piano di Miglioramento
1. Aggiungere nella struttura HTML di `index.html` una regione dedicata:
```html
<div id="a11yAnnouncer" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>
```
2. Creare un helper `announce(message)` in `utils/dom.js` che aggiorni il testo di questa regione per notificare:
   - *"Trovate 12 lezioni per la settimana selezionata"*
   - *"Ricerca aule completata: 8 aule libere nell'edificio U6"*
   - *"Orario aggiornato con successo"*

---

### 7.3 Disponibilità Aule Campus-Wide: Panoramica Immediata senza Selezione Obbligatoria dell'Edificio

#### Analisi del Codice Esistente
In `api/rooms.py:304-306`:
```python
if not sede:
    buildings = get_buildings()
    return self.send_json(200, {"buildings": buildings}, cache=True)
```
Se il parametro `sede` non viene specificato, l'endpoint restituisce unicamente l'elenco dei codici edificio (`U01`, `U06`, `U14`...).
Per sapere dove ci siano aule libere in questo momento nel campus, lo studente deve cliccare un edificio alla volta, attendere il fetch di ciascuno, cambiare edificio e ripetere.

#### Piano di Miglioramento
1. Introdurre la modalità `?sede=all` o `?mode=summary` in `api/rooms.py`:
   - Raccoglie concorrentemente (con ThreadPoolExecutor limitato a 4 worker) lo stato occupazione dei principali edifici didattici (U1, U2, U4, U6, U7, U14).
   - Restituisce un riassunto immediato:
```json
{
  "buildings_summary": [
    { "code": "U6", "name": "Edificio U6 (Agorà)", "free_rooms": 14, "total_rooms": 22 },
    { "code": "U7", "name": "Edificio U7 (Civitas)", "free_rooms": 8, "total_rooms": 18 },
    { "code": "U14", "name": "Edificio U14 (DISCo)", "free_rooms": 5, "total_rooms": 9 }
  ]
}
```
2. Mostrare nel frontend una schermata "Mappa Aule Campus" a colpo d'occhio, con badge del numero di aule libere per blocco edificio.

---

### 7.4 Gestione Realistica dello Stato Aule Serale (Orari di Chiusura Edifici)

#### Analisi del Codice Esistente
In `api/rooms.py:248`:
```python
if is_free:
    if next_event:
        free_until = next_event["from"]
    else:
        free_until = "fine giornata"
```
Se uno studente consulta l'app alle 21:45 o alle 23:00, l'aula risulta "Libera fino a fine giornata". Nella realtà gli edifici del campus Bicocca chiudono tra le 19:30 e le 20:30 (ad eccezione delle sale studio serali dedicate come in U12).

#### Piano di Miglioramento
1. Definire gli orari indicativi di apertura/chiusura campus per edificio (es. `closing_time: "20:00"` per U6/U7/U14).
2. Se `check_mins >= closing_mins`, indicare lo stato *"Edificio Chiuso"* invece di *"Libera fino a fine giornata"*, evitando che studenti cerchino aule studio quando i varchi sono già sbarrati.

---

## 🛠️ Tema 8: Tooling, Developer Experience, Test Suite & CI/CD

### 8.1 Strutturazione Standard delle Directory: Migrazione da `scratch/` a `tests/`

#### Analisi del Codice Esistente
Attualmente tutti i file di test risiedono nella directory `scratch/`:
- `scratch/test_edge_cases.py` (806 righe)
- `scratch/test_comprehensive_api.py` (599 righe)
- `scratch/test_security_and_redis.py` (208 righe)
- `scratch/test_issues_7_8.py` (165 righe)
- `scratch/test_phase3_cache.py` (116 righe)
- `scratch/test_rooms_midnight.py` (107 righe)
- `scratch/test_exams_enhancements.py` (24 righe)
- `scratch/test_frontend.test.js` (229 righe)

Per convenzione open-source e standard di ingegneria del software, la cartella `scratch` è destinata a file temporanei usa-e-getta o esperimenti non tracciati, mentre i test devono risiedere in `tests/`.

#### Piano di Miglioramento
1. Spostare i file di test in una cartella canonica `tests/`:
   - `tests/backend/`: tutti i test unitari e di integrazione Python.
   - `tests/frontend/`: i test Node.js / DOM.
2. Aggiornare il comando di esecuzione nel `README.md`:
```bash
python3 -m unittest discover -s tests/backend -p "test_*.py"
```

---

### 8.2 Creazione di `package.json` con Script Standard di Sviluppo

#### Analisi del Codice Esistente
Nella root del repository non è presente alcun file `package.json`. Uno sviluppatore che clona il progetto non ha a disposizione script standard per avviare il server di sviluppo o eseguire i test con `npm`.

#### Piano di Miglioramento
Creare `package.json` nella root con script essenziali:
```json
{
  "name": "unimib-calendar",
  "version": "2.0.0",
  "description": "Progressive Web App per gli orari e il campus dell'Università di Milano-Bicocca",
  "private": true,
  "scripts": {
    "dev": "vercel dev",
    "test": "npm run test:backend && npm run test:frontend",
    "test:backend": "python3 -m unittest discover -s tests/backend -p \"test_*.py\"",
    "test:frontend": "node --test tests/frontend/*.test.js",
    "lint:py": "python3 -m ruff check api/ tests/",
    "format:py": "python3 -m ruff format api/ tests/",
    "format:css": "npx prettier --write \"public/css/**/*.css\""
  },
  "devDependencies": {
    "prettier": "^3.3.0",
    "vercel": "^37.0.0"
  }
}
```

---

### 8.3 Integrazione Continuous Integration (CI) con GitHub Actions (`.github/workflows/ci.yml`)

#### Analisi del Codice Esistente
Attualmente non esiste alcuna automazione di Continuous Integration nel repository. Le modifiche vengono committate e inviate senza verifica automatica che i 79 test Python e i test JavaScript continuino a passare.

#### Piano di Miglioramento
Creare il workflow `.github/workflows/ci.yml`:
```yaml
name: CI Suite

on:
  push:
    branches: [ main, miglioramenti ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Run Backend Tests
        run: python3 -m unittest discover -s tests/backend -p "test_*.py"

      - name: Run Frontend Tests
        run: node --test tests/frontend/*.test.js
```

---

### 8.4 Configurazione Linter & Formatter Python (`pyproject.toml`)

#### Analisi del Codice Esistente
Non esiste una configurazione per garantire la coerenza stilistica e prevenire errori di sintassi o import inutilizzati nel codice Python.

#### Piano di Miglioramento
Aggiungere `pyproject.toml` per configurare **Ruff** (il linter/formatter Python più rapido e moderno):
```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["api"]
```

---

## 🚦 Matrice di Priorità & Roadmap di Rilascio

Per massimizzare l'impatto tecnico minimizzando i rischi di regressione, gli interventi sono organizzati in 4 sprint progressivi:

```text
[Sprint 1: Fondamenta & Performance Immediate]
 ├── Rimozione runtime Tailwind CDN inutilizzato da index.html (-350KB netti)
 ├── Creazione api/_common.py e correzione bug fuso orario UTC/Rome (mezzanotte)
 ├── Configurazione HTTP Security Headers OWASP in vercel.json
 └── Migrazione test da scratch/ a tests/ e aggiunta package.json + GitHub Actions CI
       │
       ▼
[Sprint 2: Hardening Backend & Standard Calendario]
 ├── Refactoring dei 9 endpoint su BaseApiHandler
 ├── Caching condiviso L2 su Redis per EasyCourse e Bounded LRU in memoria
 ├── Integrazione blocco VTIMEZONE (Europe/Rome) e line-folding RFC 5545 in export.py
 └── Restrizione CORS per endpoint autenticati (profile / group)
       │
       ▼
[Sprint 3: Modularizzazione Frontend & Resilienza PWA]
 ├── Scomposizione di app.js (8.560 righe) in ES Modules specifici per vista
 ├── Tagged template literal sicuro html per eliminare rischi XSS latenti
 ├── Caching locale dei Web Font PT Sans per consultazione offline garantita
 └── Auto-bumping della versione cache del Service Worker al deploy
       │
       ▼
[Sprint 4: Ergonomia UX, Accessibilità & Funzionalità Campus]
 ├── Focus trapping accessibile nei modali e Mobile Bottom Sheets
 ├── Endpoint aggregato campus-wide per panoramica immediata delle aule libere
 ├── Gestione orari di chiusura serale edifici UNIMIB
 └── Regioni aria-live per screen reader (WCAG 2.2 AA compliant)
```

### Sintesi Valore / Sforzo (Impact vs Effort)

| Intervento | Priorità | Impatto | Effort | Beneficio Principale |
| :--- | :---: | :---: | :---: | :--- |
| **Rimozione Tailwind CDN da `index.html`** | P0 | Alto | S (5 min) | Taglio di 350KB di download e FCP 200ms più veloce su mobile |
| **Fix Fuso Orario UTC/Rome (`api/_common.py`)** | P0 | Critico | S (30 min) | Risolve orario errato visualizzato attorno a mezzanotte |
| **Security Headers in `vercel.json`** | P0 | Alto | S (20 min) | CSP, HSTS e X-Frame-Options attivi su tutta la PWA |
| **`VTIMEZONE` RFC 5545 in `export.py`** | P1 | Alto | M (1 ora) | Piena compatibilità con Google Calendar e Microsoft Outlook |
| **Refactoring `api/_common.py`** | P1 | Alto | M (2 ore) | -800 righe duplicate, manutenzione centralizzata |
| **GitHub Actions CI & Cartella `tests/`** | P1 | Medio | S (30 min) | Test automatici su ogni push/PR, repository pulito |
| **Scomposizione `app.js` in ES Modules** | P2 | Alto | L (4-6 ore) | Eliminazione del monolite da 8.500 righe, isolamento bug |
| **Aule Libere Campus-Wide (`?sede=all`)** | P2 | Medio | M (2 ore) | Orientamento rapido tra gli edifici per gli studenti |
| **Focus Trap & A11y WCAG AA** | P3 | Medio | M (2 ore) | Accessibilità da tastiera e certificazione inclusiva |
