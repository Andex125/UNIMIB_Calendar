# 📅 Piano Definitivo di Sviluppo e Miglioramento: UNIMIB Orari

Documento programmatico unificato per l'evoluzione architetturale, tecnica ed esperienziale (UX/UI) dell'applicazione **UNIMIB Orari & Campus Companion**, Progressive Web App orientata agli studenti dell'**Università degli Studi di Milano-Bicocca**.

L'applicazione è distribuita su **Vercel** con frontend statico PWA e backend serverless in **Python**.

---

## 🧭 1. Metodologia di Lavoro e Struttura Progetto

### Flusso di Sviluppo
* **Branch di lavoro**: `miglioramenti` nel fork (`Andex125/UNIMIB_Calendar`).
* **Verifica continua**: Esecuzione locale con `vercel dev` e test su dispositivi mobili reali (iOS Safari e Android Chrome) per monitorare il comportamento effettivo di Service Worker, gesture touch e caching.
* **Svuotamento cache di test**: Hard refresh (`Ctrl+Shift+R`) o DevTools → *Application* → *Clear site data*.
* **Rilascio**: Commit atomici per fase con tracciamento convenzionale e Pull Request finale verso il repository principale (`mbroglio/UNIMIB_Calendar`).

### Struttura del Repository (Confermata)
```
.
├── api/                    # Serverless Functions Python su Vercel
│   ├── calendar.py         # Orari lezioni settimanali (EasyCourse scraper)
│   ├── exams.py            # Calendario appelli d'esame
│   ├── export.py           # Generatore export .ics, .csv, .json e feed live WebCal
│   ├── group.py            # Gestione gruppi di studio e calendari condivisi
│   ├── options.py          # Dati corsi, lauree, anni e periodi didattici
│   ├── profile.py          # Sincronizzazione profilo utente e PIN via Redis
│   ├── rooms.py            # Stato e occupazione aule in tempo reale
│   ├── shared_calendar.py  # Orari aggregati per gruppi di studio
│   └── teachers.py         # Elenco docenti e orari ricevimento/lezioni
├── public/                 # Asset statici PWA serviti alla radice del CDN
│   ├── css/style.css       # Foglio di stile principale e variabili CSS
│   ├── js/app.js           # Logica SPA, gestione stato, UI e chiamate API
│   ├── icons/              # Icone PWA multi-risoluzione
│   ├── favicon.ico
│   ├── index.html          # Markup principale SPA
│   ├── manifest.json       # Descrittore Web App Manifest
│   └── sw.js               # Service Worker PWA per gestione offline e cache
├── vercel.json             # Regole di routing, header e deploy Vercel
└── README.md               # Documentazione e istruzioni operative
```

---

## 🎨 2. Ricerca Identità Visiva e Brand Identity UNIMIB

Dall'analisi del *Brand Book*, delle linee guida ufficiali di Ateneo e dei fogli di stile del portale istituzionale `unimib.it` (`themes/custom/unimib_base/css/style.css`), sono stati estratti i riferimenti grafici istituzionali da implementare.

### 2.1 Colori Istituzionali di Ateneo
* **Rosso Bicocca / Granata (Primario)**: `#A71E3B` (RGB: `167, 30, 59`). Colore distintivo dell'Ateneo, da utilizzare per l'header, gli stati attivi e gli accenti principali.
* **Bordeaux Scuro (Ombre & Contrasti)**: `#730723` (RGB: `115, 7, 35`). Utilizzato per bordi, gradienti e accenti ad alto contrasto.
* **Rosso Accento / Hover**: `#C42649` / `#D83424`.
* **Grigio Ottaedro**: `#A5A6A7` (RGB: `165, 166, 167`). Tonalità ufficiale dell'emblema geometrico in scala di grigi.
* **Nero Istituzionale**: `#1D1D1B` (RGB: `29, 29, 27`). Tono scuro e bilanciato per testi e superfici in Dark Mode.
* **Superficie Chiara (Light Mode)**: `#F8FAFC` / `#FFFFFF`.

### 2.2 Colori Ufficiali delle Aree Didattiche UNIMIB
Nei CSS ufficiali di Ateneo, ogni macro-area disciplinare possiede un codice cromatico identificativo standard:
* 📊 **Economico-Statistica**: Giallo Oro `#E5C200`
* ⚖️ **Giuridica**: Blu Indaco `#005096`
* 🔬 **Scientifica (Informatica, Matematica, Fisica, Biologia, ecc.)**: Verde Smeraldo `#00753B`
* 🩺 **Medica (Medicina, Chirurgia, Infermieristica)**: Rosso Scarlatto `#D83424`
* 🌐 **Sociologica**: Arancione `#F29400`
* 🧠 **Psicologica**: Rubino / Magenta Scuro `#A4224B`
* 🎓 **Scienze della Formazione**: Viola / Fucsia `#B82585`

> *Nota*: La mappatura dei corsi e delle card sulle tonalità dell'area di appartenenza sostituisce la vecchia palette generica Tailwind Purple (`#8B5CF6`), offrendo un orientamento visivo immediato a colpo d'occhio.

### 2.3 Simboli e Iconografia del Campus
* **Ottaedro Leonardesco**: Marchio storico dell'Università degli Studi di Milano-Bicocca (ispirato al *De Divina Proportione* di Luca Pacioli con disegni di Leonardo da Vinci). Da integrare come elemento vettoriale SVG nell'header, nella favicon e come spinner geometrico di caricamento.
* **Codici Edificio ("U1...U28")**: Il campus di Bicocca (progettato su schema Gregotti) identifica ogni struttura con la nomenclatura "U" (es. *U6* sede centrale/aule magne, *U7* economia/giurisprudenza, *U14* informatica, *U1/U2* scienze). I badge delle lezioni e delle aule devono evidenziare con precisione il blocco edificio.
* **Tipografia di Ateneo**: *PT Sans* e *PT Sans Narrow* (font web ufficiali di Ateneo da integrare tramite Google Fonts).

---

## 🛠️ 3. Paradigmi e Framework Consigliati

1. **Alpine.js (Reattività leggera, ~15kB)**:
   * Consente di eliminare la manipolazione imperativa diretta del DOM (`style.display`, `classList.toggle`, query manuali) in `app.js`.
   * Gestione dichiarativa di modali, bottom sheet, tab dei giorni, filtri e pannelli direttamente nell'HTML.
2. **Design Tokens & CSS Custom Properties Modulari**:
   * Centralizzazione di spaziature, raggi di curvatura, tipografia e palette istituzionale Bicocca tramite variabili CSS standard (`--bicocca-red`, `--bicocca-surface`, ecc.).
   * Predisposizione nativa al passaggio dinamico Dark Mode / Light Mode senza duplicare classi.
3. **Lucide Icons (Vettoriali SVG)**:
   * Rimpiazzo delle emoji eterogenee di sistema con un set coerente, compatto e accessibile di icone SVG (omogenee su iOS, Android, macOS e Windows).

---

## 📋 4. Roadmap Integrata delle Attività

### PARTE I: Interventi Tecnici, Caching e PWA Baseline *(Completati)*

#### Fase 1: Frontend Baseline & Bugfix UX (`style.css`, `app.js`, `index.html`)
- [x] **Layout Desktop Centrato**: Creazione del wrapper `.app-shell { max-width: 720px; margin-inline: auto; }` per centrare il contenuto su schermi ampi mantenendo `.app-header` a tutta larghezza.
- [x] **Colore Corso su Lezioni Annullate**: Aggiunto `.event-card.target.canceled { border-left-color: var(--course-color, var(--accent-purple)); }` per preservare il colore identificativo del corso anche in presenza della classe `.canceled`.
- [x] **Conteggio Pallini Giorni**: In `renderDayTabs` conteggio limitato a `isFavorite(e) && !e.is_canceled` per non mostrare indicatori ingannevoli su lezioni soppresse.
- [x] **Comportamento Dinamico "Oggi"**:
  - Selezione automatica del giorno corrente all'avvio se compreso nella settimana visualizzata, altrimenti fallback su "Tutti".
  - Il pulsante "Oggi" reimposta la settimana corrente e seleziona oggi (se domenica, seleziona "Tutti").
  - Evidenziazione con bordo dedicato del tab del giorno corrente e ridenominazione badge in "Oggi".
- [x] **Etichetta Giorni Dinamica**: Sostituita la dicitura fissa "5GG" con `${giorni.length}GG` adattata all'effettivo numero di giorni con lezioni.
- [x] **Filtro Swipe Bidirezionale**: Registrazione assi X e Y (`clientX`/`clientY`) con blocco del cambio settimana se `Math.abs(dy) > Math.abs(dx)` per consentire lo scorrimento verticale naturale della pagina.
- [x] **Pulizia Markup e Accessibilità Base**: Aggiornato testo spinner ("Carico l'orario…"), rimossi `user-scalable=no` e `maximum-scale` per rispettare le linee guida WCAG sullo zoom, rimosso ID duplicato `btnCloseQrModal`.

#### Fase 2: Service Worker & Caching Offline (`public/sw.js`, `app.js`)
- [x] **Scope Radice Service Worker**: Spostamento di `sw.js` in `public/sw.js` con registrazione sullo scope globale `/sw.js` per intercettare l'intera PWA.
- [x] **Installazione Robusta & Asset Reali**: Lista `ASSETS` allineata ai percorsi reali (`/css/style.css`, `/js/app.js`, `/manifest.json`, icone); aggiunta tolleranza ai fallimenti singoli durante il caching iniziale.
- [x] **Strategia Cache Statica**: Adozione del pattern *stale-while-revalidate* per le risorse statiche per garantire avvio istantaneo e aggiornamento trasparente dopo ogni deploy.
- [x] **Strategia Cache API**: Adozione del pattern *network-first* per gli endpoint `/api/*`, con memorizzazione in cache limitata alle risposte `GET` con esito `200 OK` (evitando di persistere risposte di errore).
- [x] **Filtro Same-Origin**: Esclusione dal Service Worker delle richieste esterne (es. generazione QR code su domini terzi).

#### Fase 3: Serverless API & Cache-Control (`api/calendar.py`, `api/options.py`)
- [x] **Cache CDN su `calendar.py`**: Aggiunto header `Cache-Control: public, s-maxage=300, stale-while-revalidate=600` sulle risposte 200 per ridurre il carico sui server UNIMIB EasyCourse senza degradare la reattività.
- [x] **Bypass Cache su Refresh Esplicito**: Gestione del parametro `refresh=1` (inviato dal pulsante 🔄) con emissione di `Cache-Control: no-store` per forzare il recupero in tempo reale.
- [x] **Gestione Errori UNIMIB**: Sostituzione degli errori generici `500` con `502 Bad Gateway` accompagnati da `Cache-Control: no-store` in caso di mancata risposta o payload non conforme da EasyCourse.
- [x] **Allineamento `options.py`**: Mantenuto `s-maxage=3600` per le opzioni con header `no-store` in caso di errore.

#### Fase 4: Export Calendario & Condivisione Avanzata (`api/export.py`, README)
- [x] **Motore Export Dedicato**: Implementazione di `api/export.py` con supporto a download iCalendar (`.ics`), file CSV per fogli di calcolo e formato JSON.
- [x] **Sottoscrizione Live WebCal**: Supporto per feed continuo `webcal://` sincronizzato automaticamente con Apple Calendar, Google Calendar e Outlook.
- [x] **Filtro Esportazione Preferiti**: Possibilità di esportare selettivamente solo le lezioni dei corsi contrassegnati come preferiti.
- [x] **Documentazione Vercel**: Allineamento del `README.md` con le istruzioni ufficiali di deploy e sviluppo locale con Vercel CLI.

---

### PARTE II: Rebranding UNIMIB, Ergonomia Mobile ed Evoluzione UX/UI *(In Programmazione)*

#### Fase 5: Rebranding Cromatico & Design System UNIMIB
- [x] **Sostituzione Colore Guida**: Rimpiazzare `--accent-purple: #8B5CF6` con le variabili di Ateneo `--bicocca-red: #A71E3B`, `--bicocca-red-dark: #730723` e `--bicocca-red-accent: #C42649`.
- [x] **Mappatura Aree Didattiche**: Assegnare alle card e alle categorie i colori ufficiali delle 7 aree UNIMIB (Economica `#E5C200`, Giuridica `#005096`, Scientifica `#00753B`, Medica `#D83424`, Sociologica `#F29400`, Psicologica `#A4224B`, Formazione `#B82585`).
- [x] **Tipografia di Ateneo**: Importare i font web ufficiali *PT Sans* e *PT Sans Narrow* da Google Fonts applicandoli a intestazioni, card orari e badge aule.
- [x] **Integrazione Ottaedro Leonardesco**: Inserire il simbolo vettoriale dell'Ottaedro nell'header principale, nella favicon ad alta risoluzione e come spinner SVG animato durante il fetch dei dati.

#### Fase 6: Supporto Tema Chiaro / Scuro (Dark & Light Mode)
- [ ] **Variabili CSS per Light Theme**: Creare il set complementare di token cromatici chiari (`--bg-primary: #F8FAFC`, `--bg-surface: #FFFFFF`, `--text-primary: #1D1D1B`, con accenti e bordi in Rosso Bicocca).
- [ ] **Rilevamento Automatico e Toggle Manuale**: Supportare `prefers-color-scheme` del sistema operativo con salvataggio della preferenza utente in `localStorage` e toggle rapido nell'header.
- [ ] **Contrasto Solare Campus**: Ottimizzare i livelli di contrasto per garantire perfetta leggibilità all'aperto nei cortili e nelle piazze del polo Bicocca.

#### Fase 7: Iconografia Vettoriale & Badge Edifici Campus
- [ ] **Sostituzione Emoji con Lucide Icons**: Rimpiazzare le emoji di sistema (📅, 🧑‍🏫, 🏫, 📝, 👥, ⭐, 🔍, 📥, ⚙️) con icone SVG nitide, uniformi e accessibili.
- [ ] **Badge Edificio Dedicati ("U")**: Evidenziare nelle card delle lezioni e nella vista Aule il blocco campus di appartenenza (pill dedicate `U6`, `U7`, `U14`, ecc.) con codice cromatico coerente.
- [ ] **Link Geografico Campus**: Aggiungere sulle card delle aule un pulsante di geolocalizzazione rapida che apra la posizione dell'edificio su mappa (OpenStreetMap / Google Maps) con le coordinate esatte del campus Bicocca.

#### Fase 8: Ergonomia Mobile & Micro-Interazioni
- [ ] **Bottom Sheet su Smartphone**: Convertire le modali (`setupModal`, `roomScheduleModal`, `exportModal`, `shareModal`) in fogli scorrevoli dal basso su schermi touch (ottimizzazione *thumb zone*), mantenendo la finestra di dialogo centrata su desktop.
- [ ] **Skeleton Screens**: Rimpiazzare lo spinner di attesa con placeholder scheletrici pulsanti che riflettano la struttura delle card, azzerando la percezione di latenza.
- [ ] **Gesture Pull-to-Refresh**: Implementare il trascinamento verso il basso su mobile per forzare l'aggiornamento immediato degli orari (invocando la chiamata con `refresh=1`).
- [ ] **Widget "Adesso / Prossima Lezione"**: Inserire in evidenza all'inizio della vista orario un riquadro riassuntivo che segnali la lezione attualmente in corso o la successiva con aula, orario e conto alla rovescia.

#### Fase 9: Navigazione, Ricerca Avanzata & Accessibilità (A11y)
- [ ] **Mini-Calendario di Navigazione**: Aggiungere un selettore compatto a calendario per saltare rapidamente a specifiche settimane o mesi futuri.
- [ ] **Ricerca con Debounce ed Evidenziazione**: Ottimizzare il campo di ricerca con debounce visivo ed evidenziazione evidenziata (*text highlighting*) delle corrispondenze trovate (docente, materia, aula).
- [ ] **Indicatore Stato Offline**: Mostrare un banner non invasivo di avviso (*"Modalità Offline - Dati salvati"*) quando la connettività si interrompe nelle aule seminterrate.
- [ ] **Accessibilità WCAG AA**: Implementare attributi ARIA (`role="tablist"`, `role="tab"`, `role="dialog"`, `aria-label`), assicurare ratio di contrasto minimo 4.5:1 e focus ring visibile per navigazione interamente da tastiera.

#### Fase 10: Modernizzazione Architetturale del Frontend
- [ ] **Adozione Incrementale Alpine.js**: Riorganizzare la logica di gestione modali, filtri corsi e commutazione schede eliminando il codice procedurale ridondante in `app.js`.
- [ ] **Standardizzazione Design Tokens**: Consolidare le definizioni CSS per facilitare manutenzione ed estensibilità future del progetto.

---

## 🚦 5. Priorità e Sequenza di Esecuzione Consigliata

```text
[Completato] Fasi 1, 2, 3, 4: Baseline PWA, Cache SW, Serverless API e Motore Export
      │
      ▼
[Priorità 1] Fasi 5 & 7: Rebranding Ufficiale Bicocca + Icone SVG Lucide + Badge Edifici "U"
      │       (Massimo impatto visivo immediato e forte identità di Ateneo a basso costo di sviluppo)
      ▼
[Priorità 2] Fasi 6 & 8: Supporto Light Mode + Bottom Sheet Mobile + Skeleton Loading + Widget "Adesso"
      │       (Ergonomia mobile ottimale per l'utilizzo sul campo tra le aule del campus)
      ▼
[Priorità 3] Fasi 9 & 10: Navigazione a calendario, Ricerca con highlight, Accessibilità WCAG e Alpine.js
              (Rifinitura architetturale e inclusività completa)
```

---

## 📌 6. Sintesi delle Decisioni e Punti Risolti

| Questione | Stato | Risoluzione Adottata |
| :--- | :---: | :--- |
| **Struttura cartelle** | Risolto | Confermato standard con asset statici in `public/` e funzioni serverless in `api/`. |
| **Comportamento "Oggi"** | Risolto | Seleziona il giorno odierno all'avvio e al clic sul pulsante dedicato; seleziona "Tutti" se oggi è domenica o fuori intervallo. |
| **Cache API su CDN** | Risolto | 5 minuti di cache (`s-maxage=300`) con bypass immediato `no-store` su richiesta esplicita `refresh=1`. |
| **Esportazione Calendario** | Risolto | Modulo dedicato `api/export.py` con supporto per .ics, .csv, .json e abbonamento WebCal. |
| **Identità Visiva** | Definita | Mappatura completa su palette ufficiale di Ateneo (Rosso Granata `#A71E3B`, Ottaedro e 7 aree didattiche). |
