# Piano Maestro di Rinnovamento UI/UX ed Estetica — UNIMIB Calendar

> **Fondamento Teorico**: Nielsen Norman Group (NN/g), *Refactoring UI* (Adam Wathan & Steve Schoger), Apple Human Interface Guidelines (iOS 18 / macOS Sequoia), Material Design 3 (M3), ed ergonomia cognitiva applicata alla vita universitaria (microsessioni < 20 secondi).

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

## 5. Piano Operativo di Esecuzione Punto per Punto

Il lavoro è suddiviso in 4 sprint incrementali e verificabili, senza interruzioni di servizio:

```
[Sprint 1: Design System & Shell] ➔ [Sprint 2: Timetable & Hero Widget] ➔ [Sprint 3: Aule, Docenti, Esami] ➔ [Sprint 4: Modali & Rifinitura]
```

### Sprint 1: Fondamenta del Design System, Header e Floating Dock
- [ ] Aggiornare `:root` in `public/css/style.css` con i nuovi token colore Zinc / Frost e curve `--ease-spring`.
- [ ] Ridisegnare `.app-header` con sfocatura traslucida e raggruppamento delle icone in capsula unica.
- [ ] Convertire `.bottom-nav` in **Floating Island Dock** sospesa con pillola attiva e bordi arrotondati `rounded-full`.
- [ ] Verificare accessibilità contrasto colori (WCAG AA su tutti i bottoni).

### Sprint 2: Core Timetable & Hero "Now/Next" Widget
- [ ] Riprogettare il blocco navigatore settimana a capsula unificata.
- [ ] Trasformare la barra dei giorni in un carousel tattile a scorrimento con dot-indicators colorati.
- [ ] Riscrivere il template HTML/CSS di `.event-card`:
  - Adozione del layout Bento (badge orario tabulare, titolo a peso 700, chip Docente + Aula).
  - Sfumatura di fondo coordinata al colore corso con opacità controllata.
- [ ] Creare la **Hero Card "Adesso / Prossima Lezione"** dinamica con barra di completamento orario in tempo reale e stato radar.

### Sprint 3: Ottimizzazione Visiva Viste Aule, Docenti ed Esami
- [ ] Introdurre i filtri a pillola per gli edifici nelle aule e i badge a semaforo (Libera/Occupata con orario limite).
- [ ] Rinnovare la card docente con avatar a gradiente e accordion compatto.
- [ ] Introdurre il badge countdown dinamico negli appelli d'esame.

### Sprint 4: Modali Bottom-Sheet, Skeleton Loaders e Micro-animazioni
- [ ] Convertire tutti i modali in Bottom Sheets nativi per schermi mobili (< 768px).
- [ ] Sostituire i testi di caricamento grezzi con componenti skeleton a effetto shimmer (`.skeleton-card`, `.skeleton-pill`).
- [ ] Aggiungere feedback tattile attivo (`scale(0.97)`) su tutti i pulsanti e le schede interattive.
- [ ] Eseguire collaudo visivo e verifica funzionale completa con suite di test.
