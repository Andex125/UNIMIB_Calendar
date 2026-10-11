# Piano Maestro di Rinnovamento UI/UX, Sicurezza e Resilienza — UNIMIB Calendar

> **Fondamento Teorico**: Nielsen Norman Group (NN/g), *Refactoring UI* (Adam Wathan & Steve Schoger), Apple Human Interface Guidelines (iOS 18 / macOS Sequoia), Material Design 3 (M3), OWASP Top 10 API Security (2023-2026), e Defensive UX / Poka-Yoke per prevenzione degli errori umani.

---

## 1. Audit Euristico e Diagnosi UX/UI della Codebase Attuale

Un'analisi condotta su [`public/index.html`](file:///home/gigi/Documenti/UNIMIB_Calendar/public/index.html), [`public/css/style.css`](file:///home/gigi/Documenti/UNIMIB_Calendar/public/css/style.css) e [`public/js/app.js`](file:///home/gigi/Documenti/UNIMIB_Calendar/public/js/app.js) evidenzia solide fondamenta tecniche (770px desktop container, icone SVG inline, 15 colori ad alto contrasto, assenza di dipendenze pesanti), ma anche diversi attriti cognitivi e debiti estetici rispetto agli standard 2026.

### 1.1 Analisi secondo le 10 Euristiche di Nielsen & Leggi della UX
1. **Legge di Fitts & Bersagli Touch**:
   - *Criticità*: Alcuni pulsanti di azione secondaria (rimozione chip corsi esami, navigazione data) presentano aree attive ridotte (30x30px), inferiori allo standard raccomandato di **44x44px (Apple HIG)** e **48x48px (M3)**, causando errori di tocco su schermi mobili mentre si cammina in ateneo.
   - *Soluzione*: Padding di interazione trasparente (`::before` touch target expander) per mantenere l'aspetto compatto garantendo 44px di bersaglio effettivo.
2. **Riconoscimento vs Richiamo (NN/g #6) e Teoria della Microsessione**:
   - *Insight*: Lo studente apre l'orario in "microsessioni" di 15-22 secondi tra un'aula e l'altra con un solo obiettivo: *«Dove devo andare adesso? Qual è l'aula e il piano?»*.
   - *Criticità*: L'attuale widget "Adesso / Prossima" è un banner statico che richiede lettura analitica; le card lezioni presentano informazioni testuali dense ma poco scansionabili al volo.
   - *Soluzione*: Widget ridisegnato secondo la filosofia **Flighty / Live Activity** (stile gate aeroportuale con stato istantaneo, countdown dinamico e pin aula/edificio ad alta visibilità).
3. **Gerarchia Visiva e Legge della Prossimità (Gestalt & Refactoring UI)**:
   - *Criticità*: Le card lezioni usano un singolo blocco di testo con un bordo laterale. Aula, docente ed edificio competono con la stessa enfasi visiva.
   - *Soluzione*: Riorganizzazione modulare a **Bento Grid**: orario in numeri tabulari in alto a sinistra, badge materia colorato in alto a destra, titolo prominente (peso 700), metadati contestuali (Docente, Aula U6-01, Edificio) raggruppati in chip tattili distinti.
4. **Estetica e Design Minimalista (NN/g #8 & Liquid Glass)**:
   - *Criticità*: Top header e bottom nav sono blocchi opachi piatti di tipo tradizionale, ancorati in modo rigido e privi di profondità visiva.
   - *Soluzione*: Superfici "Liquid Glass" con sfocatura adattiva (`backdrop-filter: blur(20px)`), bordi translucidi a 1px (`rgba(255, 255, 255, 0.08)` in dark mode) e Floating Island dock sospesa.

---

## 2. Benchmark dei Sistemi di Riferimento di Eccellenza

| Piattaforma | Modello di Ispirazione | Elementi Architetturali da Adottare |
| :--- | :--- | :--- |
| **Flighty (Live Activity Benchmark)** | Monitoraggio status in tempo reale | Hero widget ad alto impatto per la lezione corrente: barra di completamento temporale dinamica, indicatore di stato pulsante ("In corso", "Tra 20 min"), localizzazione aula lampo. |
| **Amie & Notion Calendar (Cron)** | Pianificazione contemporanea | Selettore orizzontale a capsule temporali con scorrimento inerziale, dot-indicators multicolore per intensità del carico giornaliero, palette pastello su sfondo profondo. |
| **Linear App** | Design system Dark Mode premium | Superfici zinc/ardesia (`#090D16`), micro-riflessi luminosi sui bordi delle card attive, pulsanti con micro-transizioni a molla (`cubic-bezier(0.16, 1, 0.3, 1)`). |
| **Apple HIG (iOS 18)** | Navigazione mobile e contenimento | Floating Navigation Dock inferiore (non attaccata al bordo schermo), modali convertiti in Bottom Sheets a trascinamento naturale con maniglia di presa (`drag handle`). |
| **Refactoring UI** | Tipografia e spaziatura sistematica | Gerarchia costruita mediante **peso e sfumatura** piuttosto che con sole dimensioni font; uso rigoroso della scala metrica a multipli di 4px (4, 8, 12, 16, 20, 24, 32px). |

---

## 3. Specifiche Tecniche del Nuovo Design System

### 3.1 Token di Colore e Superfici (WCAG 2.2 AAA / AA Compliant)

```css
/* --- DARK THEME: Zinc Titanium & Liquid Glass --- */
:root[data-theme="dark"], :root {
  --canvas-bg: #090D16;                  /* Sfondo primario profondo */
  --surface-base: #111827;                /* Sfondo card base */
  --surface-elevated: #1F293D;            /* Sfondo card in rilievo / hover */
  --surface-glass: rgba(17, 24, 39, 0.78); /* Vetro per Header e Dock */
  --surface-glass-border: rgba(255, 255, 255, 0.08); /* Bordo ultra-fine 1px */
  
  --text-primary: #F8FAFC;                /* 100% leggibilità titoli */
  --text-secondary: #94A3B8;              /* Metadati e orari secondari */
  --text-tertiary: #64748B;               /* Icone passive e separator */

  --bicocca-primary: #A71E3B;             /* Rosso Bicocca identitario */
  --bicocca-glow: rgba(167, 30, 59, 0.45);/* Glow decorativo */
  --status-live: #10B981;                 /* Verde smeraldo attivo */
  --status-live-bg: rgba(16, 185, 129, 0.14);
}

/* --- LIGHT THEME: Frost & Crisp Slate --- */
:root[data-theme="light"] {
  --canvas-bg: #F8FAFC;                  /* Bianco ottico morbido */
  --surface-base: #FFFFFF;                /* Card candide */
  --surface-elevated: #F1F5F9;            /* Hover e chip secondari */
  --surface-glass: rgba(255, 255, 255, 0.88);
  --surface-glass-border: rgba(226, 232, 240, 0.9);
  
  --text-primary: #0F172A;                /* Nero profondo slate */
  --text-secondary: #475569;              /* Grigio scuro leggibile */
  --text-tertiary: #94A3B8;

  --bicocca-primary: #A71E3B;
  --bicocca-glow: rgba(167, 30, 59, 0.2);
  --status-live: #059669;
  --status-live-bg: rgba(5, 150, 105, 0.12);
}
```

### 3.2 Tipografia e Numeri Tabulari
- **Orari e codici**: Adozione universale di `font-variant-numeric: tabular-nums` e `letter-spacing: -0.02em` per evitare oscillazioni orizzontali nei countdown e negli elenchi orari.
- **Micro-scala**:
  - `Display / Hero`: 1.25rem (20px), peso 800, line-height 1.2.
  - `Card Title`: 0.95rem (15.2px), peso 700, line-height 1.35.
  - `Badges & Timestamps`: 0.78rem (12.5px), peso 600, maiuscoletto soft.
  - `Caption & Hints`: 0.70rem (11.2px), peso 500.

### 3.3 Micro-interazioni e Curve di Transizione
Tutte le transizioni seguono la curva fisica elastica di Apple e Linear:
```css
--ease-spring: cubic-bezier(0.16, 1, 0.3, 1);
--transition-card: transform 220ms var(--ease-spring), box-shadow 220ms var(--ease-spring), border-color 220ms ease;
```

---

## 4. Riprogettazione Schermata per Schermata

### 4.1 Header Superiore (Sticky Glass Navbar)
- **Visual Design**: Altezza snellita a 58px. Sfondo in vetro traslucido (`backdrop-filter: blur(20px)`), con bordo inferiore sottile e progressivo.
- **Elementi**:
  - Logo Ateneo con micro-glow al passaggio del mouse.
  - Title group: "UNIMIB Orari" con badge corso compatto a capsula.
  - Cluster Azioni Destra: raggruppamento dei controlli (Tema, Condividi, Profilo) in una capsula bento unificata ad angoli arrotondati, evitando bottoni sparsi.

### 4.2 Hero Widget "Adesso / Prossima Lezione" (Flighty Style)
- **Concetto**: Prima card visibile all'apertura dell'app.
- **Stato "In Corso"**:
  - Indicatore radar verde smeraldo pulsante (`animation: radar-pulse 2s infinite`).
  - Materia, Docente, Edificio e Aula a caratteri chiari.
  - **Timeline Progress Bar**: Barra di avanzamento orizzontale sottile (3px) con gradiente che visualizza la percentuale di lezione trascorsa (es. 65% completato, -35 min alla fine).
  - Tasto rapido: "Mappa Aula" con apertura immediata del piano/edificio.
- **Stato "Pausa / Tra poco"**:
  - Visualizzazione rilassata: countdown all'inizio della lezione successiva con orario di inizio in risalto.
- **Stato "Giornata Conclusa"**:
  - Grafica minimale con spunta e promemoria della prima lezione di domani.

### 4.3 Navigatore Temporale & Carousel Giorni
- **Segmented Control Settimana**:
  - Tasti `Prec` e `Succ` integrati con l'indicatore data in una pillola monolitica centrale.
  - Badge "Oggi" sensibile al contesto: se l'utente naviga nel passato/futuro, appare un badge fluttuante pulsante "Torna a Oggi" con un clic.
- **Day Selector Touch-Slider (iOS Calendar Style)**:
  - Riga orizzontale a scorrimento fluido:
    - Ogni giorno è una capsula verticale: Sigla giorno (LUN, MAR), Data numerica (14, 15), Dot indicatore multicolore (pallini colorati corrispondenti ai corsi previsti in quel giorno).
    - Il giorno selezionato diventa una pillola in contrasto puro con animazione di scorrimento laterale.

### 4.4 Card Lezione (Bento Event Card)
- **Architettura a Zone**:
  1. *Fascia di stato*: Invece del solo bordo sinistro, una delicata sfumatura di fondo con opacità al 12% del colore del corso, con bordo laterale curvo da 4px.
  2. *Top Bar della Card*: Badge orario a contrasto elevato (es. `09:30 - 11:30`) a sinistra; Chip codice e materia a destra.
  3. *Titolo*: Nome insegnamento con contrasto pieno e leggibilità massima.
  4. *Bottom Chips Bar*: Due capsule cliccabili:
     - `[Docente]`: Icona persona + Cognome del docente (cliccando si apre l'orario del docente).
     - `[Aula]`: Icona mappa + Sigla Aula ed Edificio (es. `U6 - Aula 04`, cliccando si apre la scheda aula).
- **Stato Annullato**:
  - Trattamento visivo inequivocabile: opacità 60%, testo sbarrato sul titolo, badge rosso corallo "Lezione Annullata" in primo piano.

### 4.5 Viste Secondarie (Aule, Docenti, Esami)
- **Aule (Real-Time Campus Rooms)**:
  - Schede aule con indicatore cromatico a semaforo inequivocabile:
    - **Verde**: *Libera fino alle [Orario]* (con barra oraria rimanente).
    - **Rosso**: *Occupata da [Materia]* (fino alle [Orario]).
  - Filtro rapido a scorrimento orizzontale per Edificio (U1, U2, U3, U4, U6, U7, U14, U28...).
- **Docenti (Faculty Directory)**:
  - Avatar tipografico con iniziali su gradiente dell'area didattica (Economia, Scientifica, Medica...).
  - Accordion delle lezioni suddiviso per corso di laurea senza sovraccaricare la pagina.
- **Esami (Appelli Countdown)**:
  - Card esami con badge countdown prominente (`-12 giorni`) per rapido calcolo mentale.
  - Distinzione immediata tra appelli scritti e orali.

### 4.6 Floating Island Dock (Bottom Navigation Bar)
- **Sostituzione Bottom Bar Tradizionale**:
  - Rimozione della barra ancorata al fondo finestra a tutta larghezza.
  - Introduzione di una **Floating Island Nav** sospesa:
    - Posizionamento: `fixed; bottom: 14px; left: 50%; transform: translateX(-50%); width: calc(100% - 28px); max-width: 480px;`.
    - Finitura: `border-radius: 9999px; backdrop-filter: blur(24px); box-shadow: 0 12px 36px -4px rgba(0,0,0,0.35);`.
    - Tab attivi con pillola di sfondo che scivola con transizione fluida e icona SVG con micro-sollevamento di 2px.

### 4.7 Modali e Dialoghi (Mobile Bottom Sheets)
- **Comportamento Responsive**:
  - Su Desktop (> 768px): Dialogo centrato con ingresso a dissolvenza e scala (`scale(0.96) -> scale(1)`), angoli `20px`.
  - Su Mobile (< 768px): Trasformazione automatica in **Bottom Sheet** ancorato al basso con maniglia di presa (`drag handle`), bordo superiore arrotondato (`rounded-t-3xl`) e chiusura immediata con trascinamento o tocco sullo sfondo.

### 4.8 Skeleton Shimmer Loaders
- **Eliminazione dei blocchi "Caricamento..."**:
  - Durante il fetch dei corsi, aule o esami, la UI presenta scheletri delle card animate con gradiente shimmer traslante (`shimmer 1.5s infinite linear`), mantenendo invariata la geometria della pagina e azzerando il layout shift (CLS = 0).

---

## 5. Architettura di Sicurezza Applicativa & Difesa da Minacce (OWASP Top 10)

L'analisi della superficie di attacco delle API (`api/profile.py`, `api/group.py`, `api/shared_calendar.py`, `api/calendar.py`, `api/rooms.py`, `api/export.py`) e del client richiede l'adozione sistematica dei controlli di sicurezza OWASP.

```
       [ Client Browser ]
               │  (1) CSP, Subresource Integrity, XSS Sanitization, Debounce/Abort
               ▼
   [ Reverse Proxy / Edge ]
               │  (2) HTTP Security Headers, WAF rules, Global Rate Limiting
               ▼
     [ API Backend Python ]
               │  (3) Input Whitelist Regex, Payload Size Limit (64KB), BOLA Protection
               ├─────────────────────────┐
               ▼                         ▼
   [ Upstash Redis / Fallback ]   [ Upstream UNIMIB ]
   (4) Brute Force Lockout        (5) SSRF Whitelist (*.unimib.it)
       PBKDF2 Salting, HMAC           Timeout (8s), Circuit Breaker
```

### 5.1 Prevenzione SSRF (Server-Side Request Forgery)
- **Minaccia**: Un attaccante manipola endpoint come `/api/calendar`, `/api/export` o `/api/rooms` per forzare il server ad effettuare richieste HTTP verso reti interne, server cloud di metadati (es. `169.254.169.254`), o IP privati.
- **Contromisura Rigorosa**:
  - **URL Hardcoding & Whitelist Dominio**: Le chiamate upstream devono usare URL radice fisse e non manipolabili (`https://gestioneorari.didattica.unimib.it/...`).
  - **Validazione dei Parametri via Allowlist**:
    - `anno`: stringa fissa o regex `^\d{4}$` (es. `2024`).
    - `corso`: codice CdL formato alfanumerico stretto `^[A-Z0-9_-]{3,12}$` (es. `F1801Q`).
    - `date`: regex formato data `^\d{2}-\d{2}-\d{4}$`.
    - Rifiuto immediato (HTTP 400) con log di allerta per qualsiasi parametro che contenga caratteri sospetti (`/`, `@`, `\`, `://`).

### 5.2 Difesa da ReDoS (Regular Expression Denial of Service)
- **Minaccia**: Espressioni regolari con backtracking catastrofico su input utente lunghi (es. nomi corsi, nickname, note) possono bloccare i worker Python al 100% di CPU.
- **Contromisura**:
  - Troncare sempre le stringhe prima di applicare regex: `raw_val[:100]`.
  - Evitare quantificatori annidati `(a+)+` o `(.*a)+`. Usare pattern lineari prefissati atomici o parsing diretto.

### 5.3 Mitigazione DoS & Quota Exhaustion (Rate Limiting su Due Livelli)
- **Minaccia**: Scraping massivo o bot che esauriscono i crediti di Upstash Redis o portano al blocco dell'IP del server da parte del firewall d'Ateneo.
- **Contromisura**:
  - **Livello 1: Rate Limiting Credenziali (Login & Recovery)**:
    - Già implementato: massimo 5 tentativi errati ogni 10 minuti (`ratelimit:login:<clean_nick>`).
    - Estensione al fallback locale `/tmp/unimib_kv_store.json` per garantire parità di sicurezza.
  - **Livello 2: Throttling Chiamate Upstream**:
    - Cache in-memory con TTL di 300s su tutte le chiamate griglia/aule.
    - Se due richieste identiche arrivano contemporaneamente, solo una va a monte (Request Coalescing).
  - **Livello 3: Limite Dimensione Payload (Memory Exhaustion)**:
    - Tutte le richieste POST/PUT verificano l'header `Content-Length`.
    - Rifiuto con HTTP 413 (Payload Too Large) per corpi richiesta superiori a 64 KB.

### 5.4 Protezione BOLA (Broken Object Level Authorization) e Sessioni
- **Autenticazione**: Token di sessione crittograficamente sicuri (256-bit entropy via `secrets.token_urlsafe(32)`).
- **Separazione Netta**:
  - *Codice Condivisione Amico (es. `K9X2P4`)*: Permesso di **sola lettura** dello schedule pubblico. Impossibile accedere a PIN, token di sessione o gruppi privati.
  - *Modifica Profilo / Gruppi*: Richiede `Authorization: Bearer <session_token>`. Verifica costante del proprietario dell'account.
- **Verifica Temporale Costante**: Tutte le comparazioni di hash, PIN o token usano `hmac.compare_digest` per azzerare vulnerabilità a timing attacks.

### 5.5 Intestazioni di Sicurezza HTTP (Hardening Headers)
Tutte le risposte HTTP del server devono includere gli header raccomandati da OWASP Secure Headers Project:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://gestioneorari.didattica.unimib.it https://*.upstash.io; frame-ancestors 'none';
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

---

## 6. Defensive UX & Poka-Yoke: Prevenzione dell'Utilizzo Erroneo

La sicurezza e l'usabilità convergono nel principio giapponese **Poka-Yoke** (poka: errore involontario, yoke: evitare). L'interfaccia deve guidare l'utente ed evitare che manovre distratte corrompano i dati.

### 6.1 Ripristino Automatico da LocalStorage Corrotto (Self-Healing State)
- **Rischio**: Se l'utente chiude la pagina durante una scrittura o se una versione aggiornata dell'app modifica lo schema JSON, `JSON.parse(localStorage.getItem('unimib_config'))` può sollevare un'eccezione non gestita, causando uno schermo bianco perenne (White Screen of Death).
- **Soluzione Architetturale**:
  ```javascript
  function safeLoadConfig() {
    try {
      const raw = localStorage.getItem('unimib_config');
      if (!raw) return getDefaultConfig();
      const parsed = JSON.parse(raw);
      // Validazione schema difensiva
      return validateAndMigrateConfig(parsed);
    } catch (err) {
      console.warn("Storage corrotto rilevato. Ripristino sicuro in corso...", err);
      // Backup del dato grezzo per eventuale diagnosi e reset sicuro
      localStorage.setItem('unimib_config_backup', localStorage.getItem('unimib_config'));
      const fresh = getDefaultConfig();
      localStorage.setItem('unimib_config', JSON.stringify(fresh));
      showToast("Configurazione locale ripristinata in modo sicuro.", "warning");
      return fresh;
    }
  }
  ```

### 6.2 Prevenzione Race Conditions nelle Ricerche (Debounce + AbortController)
- **Rischio**: Lo studente digita rapidamente nel campo di ricerca docenti o aule. Richieste multiple partono in sequenza. A causa della latenza asincrona di rete, una richiesta precedente più lenta può sovrascrivere l'ultimo risultato digitato (Out-of-Order Execution).
- **Soluzione**:
  - Debounce a 280ms su ogni input di digitazione.
  - Utilizzo di `AbortController` globale per annullare le richieste HTTP in volo precedenti prima di lanciarne una nuova.

### 6.3 Tolleranza all'Assenza di Rete (Offline Resilience Banner)
- **Rischio**: La connessione Wi-Fi d'Ateneo ("eduroam") può avere cadute improvvise tra gli edifici. L'utente rischia di vedere una schermata vuota d'errore pensando che il calendario sia stato cancellato.
- **Soluzione**:
  - Listener su `window.addEventListener('offline', ...)` e `online`.
  - Comparsa di una pillola discreta in alto: `[Cloud Offline] Sei offline — Mostro l'ultimo orario salvato in cache`.
  - Nessun blocco dell'interfaccia; i dati salvati in LocalStorage rimangono consultabili fluidamente.

### 6.4 Azioni Distruttive Protette da Conferma Modale
- Azioni irreversibili (Uscita dal gruppo condiviso, Disconnessione profilo con rimozione dati locali, Cancellazione di tutti i corsi seguiti):
  - Proibito l'effetto immediato su clic accidentale.
  - Apertura di una modale di conferma bento con opzione secondaria neutra ("Annulla") e pulsante principale distruttivo evidenziato in rosso ("Elimina").

### 6.5 Sanitizzazione Client-Side e Vincoli di Maschera
- Input Codice Gruppo / Amico:
  - Maschera automatica in maiuscolo (`text-transform: uppercase`).
  - Caratteri ammessi solo alfanumerici non ambigui (rimozione automatica di spazi, simboli e lettere non ammesse).
  - Massimo 10 caratteri per evitare overflow di memoria.

---

## 7. Piano Operativo di Esecuzione Punto per Punto (Roadmap 5 Sprint)

Il piano integra sinergicamente rinnovamento visivo, potenziamento ergonomico e hardening di sicurezza:

```
[Sprint 1: Security & Hardening Core]
      │
      ▼
[Sprint 2: Design System & Shell Estetica]
      │
      ▼
[Sprint 3: Timetable Bento & Hero Live Widget]
      │
      ▼
[Sprint 4: Aule, Docenti, Esami & Poka-Yoke UX]
      │
      ▼
[Sprint 5: Mobile Bottom Sheets, Shimmer & Collaudo Totale]
```

### Sprint 1: Security Hardening & Convalida Input
- [ ] Includere gli HTTP Security Headers raccomandati (`CSP`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) nei gestori HTTP di tutte le API.
- [ ] Implementare la whitelist rigorosa dei parametri (regex CdL, anno, data) e il blocco SSRF a monte in `api/calendar.py`, `api/rooms.py`, `api/export.py`.
- [ ] Introdurre limite dimensione payload (max 64KB con HTTP 413) su tutte le richieste POST/PUT in `api/profile.py` e `api/group.py`.
- [ ] Aggiungere sanitizzazione stringhe Unicode ed estendere il rate limiting locale nel fallback `/tmp/unimib_kv_store.json`.

### Sprint 2: Fondamenta del Design System, Header e Floating Dock
- [ ] Aggiornare `:root` in `public/css/style.css` con i nuovi token colore Zinc Titanium / Frost e curve `--ease-spring`.
- [ ] Ridisegnare `.app-header` con sfocatura traslucida `backdrop-filter: blur(20px)` e capsula unificata dei controlli.
- [ ] Convertire `.bottom-nav` in **Floating Island Dock** sospesa con pillola attiva e bordi arrotondati `rounded-full`.
- [ ] Verificare accessibilità contrasto colori (WCAG AA su tutti i bottoni).

### Sprint 3: Core Timetable, Bento Event Cards & Hero "Now/Next" Widget
- [ ] Riprogettare il blocco navigatore settimana a capsula unificata.
- [ ] Trasformare la barra dei giorni in un carousel tattile a scorrimento con dot-indicators colorati.
- [ ] Riscrivere il template HTML/CSS di `.event-card`:
  - Adozione del layout Bento (badge orario tabulare, titolo a peso 700, chip Docente + Aula).
  - Sfumatura di fondo coordinata al colore corso con opacità controllata.
- [ ] Creare la **Hero Card "Adesso / Prossima Lezione"** dinamica con barra di completamento orario in tempo reale e stato radar stile Flighty.

### Sprint 4: Viste Campus, Poka-Yoke & Defensive UX
- [ ] Introdurre i filtri a pillola per gli edifici nelle aule e i badge a semaforo (Libera/Occupata con orario limite).
- [ ] Rinnovare la card docente con avatar a gradiente e accordion compatto.
- [ ] Introdurre il badge countdown dinamico negli appelli d'esame.
- [ ] Implementare `safeLoadConfig()` con recupero automatico da LocalStorage corrotto.
- [ ] Aggiungere debounce (280ms) e `AbortController` su tutti i campi di ricerca live per prevenire race conditions.
- [ ] Aggiungere banner "Sei offline — mostro orario salvato" al distacco della connessione di rete.

### Sprint 5: Modali Bottom-Sheet, Skeleton Shimmer Loaders e Collaudo Finale
- [ ] Convertire tutti i modali in Bottom Sheets nativi per schermi mobili (< 768px) con drag handle.
- [ ] Sostituire i testi di caricamento grezzi con componenti skeleton a effetto shimmer (`.skeleton-card`, `.skeleton-pill`).
- [ ] Proteggere le azioni distruttive (esci dal gruppo, reset orario) con modale di conferma dedicata.
- [ ] Esecuzione completa dei test di sicurezza e regressione (`scratch/test_security_and_redis.py`).
