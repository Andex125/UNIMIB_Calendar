# Piano di miglioramento: UNIMIB Orari

**Metodo:** lavoro sul branch `miglioramenti` del fork (`Andex125/UNIMIB_Calendar`). Un commit per fase. Ogni fase si prova con `vercel dev` e poi su uno smartphone reale, perché il comportamento del service worker su iOS e Android differisce da quello del desktop. Per svuotare la cache: hard refresh `Ctrl+Shift+R`, oppure DevTools → Application → Clear storage. A fine lavoro: push e Pull Request verso `mbroglio/UNIMIB_Calendar`.

**Prima di iniziare:** verificare la struttura dei file con `ls` (e `tree` se disponibile). Il README descrive una cartella `public/`, ma i file del progetto sembrano nella radice, mentre `index.html` carica `/css/style.css` e `/js/app.js`. Tutti i percorsi dei fogli successivi dipendono da questa struttura, quindi va chiarita per prima.

---

## Fase 1: frontend (`style.css`, `app.js`, `index.html`)

| # | Modifica | Come |
| --- | --- | --- |
| 1 | Layout centrato su desktop | Creare un wrapper `.app-shell { max-width: 720px; margin-inline: auto; }` attorno al contenuto. Lo sfondo di `.app-header` resta a tutta larghezza. Su mobile non cambia nulla. |
| 2 | Colore del corso sulle lezioni annullate | Aggiungere `.event-card.target.canceled { border-left-color: var(--course-color, var(--accent-purple)); }`. La causa è la shorthand `border-color` in `.event-card.canceled`, che sovrascrive il bordo colorato. |
| 3 | Pallini dei giorni | In `renderDayTabs` contare solo `isFavorite(e) && !e.is_canceled`. |
| 4 | Giorno corrente | Vedi regole sotto. |
| 5 | Etichetta "5GG" | Sostituire con `${giorni.length}GG`, oppure eliminare il numero. |
| 6 | Swipe | Registrare anche l'asse Y (`clientX`/`clientY`) e ignorare il gesto se `Math.abs(dy) > Math.abs(dx)`. |
| 7 | Pulizia | Testo spinner "Carico l'orario…"; rimuovere `user-scalable=no` e `maximum-scale` dal viewport; rimuovere l'ID duplicato `btnCloseQrModal` dal pulsante "Chiudi" (il suo comportamento resta affidato all'`onclick` inline). |

### Regole per "Oggi" (punto 4)

- All'apertura, se la settimana mostrata contiene oggi, si seleziona il giorno di oggi. Altrimenti si seleziona "Tutti".
- Il pulsante "Oggi" torna alla settimana corrente e seleziona il giorno di oggi, se presente. Se oggi è domenica (non nei tab) seleziona "Tutti".
- Cambiando settimana con Prev/Next o swipe, la selezione torna a "Tutti", come già accade ora.
- Il tab di oggi ha un bordo evidenziato.
- L'etichetta del badge diventa "Oggi" (non più "Oggi / Questa Settimana").

### Criteri di accettazione

- [x] Lezione annullata di un corso preferito: bordo sinistro del colore del corso.
- [x] Pallini dei giorni: nessun pallino per lezioni annullate.
- [x] Layout desktop: contenuto centrato, header a tutta larghezza.
- [x] Oggi a domenica: nessun errore, selezione "Tutti".
- [x] Swipe orizzontale cambia settimana; swipe verticale fa scorrere la pagina.

---

## Fase 2: service worker e cache (`sw.js`, `app.js`)

- Spostare `sw.js` alla radice del sito (o in `public/`, a seconda della struttura reale) e registrarlo con il percorso radice `/sw.js`. Ora è in `/js/` e controlla solo quello scope, quindi non intercetta la pagina principale.
- Aggiornare `ASSETS` ai percorsi reali e incrementare `CACHE_NAME` (ad esempio `unimib-calendar-v3`).
- **Installazione robusta:** `cache.addAll` fallisce per intero se un solo file restituisce 404. Verificare che ogni percorso esista; in alternativa aggiungere i file uno per uno, registrando gli errori senza bloccare l'installazione.
- File statici: *stale-while-revalidate*, così dopo un deploy non restano versioni vecchie.
- API: *network-first*, ma salvare in cache solo risposte `GET` con `response.ok` e `response.status === 200`. Questo evita di conservare errori.
- Limitare la gestione alle richieste same-origin (`new URL(event.request.url).origin === self.location.origin`). Il QR code di `api.qrserver.com` non deve passare dal service worker.

### Criteri di accettazione

- [x] Installazione del SW senza errori in DevTools.
- [x] Modalità offline (DevTools → Network → Offline) dopo il primo caricamento: l'app si apre e mostra l'ultimo orario salvato.
- [x] Dopo un deploy, la nuova versione compare al secondo caricamento.
- [x] Un errore dall'API non viene salvato in cache.

---

## Fase 3: API (`api/calendar.py`, `api/options.py`)

- **Risposte 200** di `calendar.py`: `Cache-Control: public, s-maxage=300, stale-while-revalidate=600`, per non interrogare UNIMIB a ogni richiesta.
- **Richieste con `refresh=1`** (inviate dal tasto 🔄): `Cache-Control: no-store`. Attenzione: attualmente `calendar.py` non legge il parametro `refresh`. Non serve cambiare la logica, perché la chiave di cache del CDN include la query string: la richiesta di refresh arriva all'origine e il suo risultato non viene memorizzato. Va comunque verificato che il comportamento sia quello atteso.
- **Errori di UNIMIB:** rispondere `502` con `no-store` invece di `500`. Distinguere, se utile, tra risposta non JSON e errore di rete, per messaggi più precisi nei log.
- **`options.py`:** già ha `s-maxage=3600` per le risposte di successo. Verificare che gli errori non abbiano header di cache e allineare la gestione agli errori di `calendar.py`.
- **Nota sul ritardo:** con `s-maxage=300` una lezione annullata può comparire con fino a cinque minuti di ritardo, più la cache del service worker e di `localStorage`. È accettabile, ma va tenuto presente quando si testa.

### Criteri di accettazione

- [x] Seconda richiesta identica entro cinque minuti: header `x-vercel-cache: HIT` (o equivalente) nella scheda Network.
- [x] Tasto 🔄: la richiesta con `refresh=1` non viene memorizzata.
- [x] Simulare un errore di UNIMIB: risposta `502`, nessuna cache.

---

## Fase 4: opzionale, da decidere dopo

1. Export iCal (`api/ics.py`) con le sole lezioni dei corsi preferiti.
2. Configurazione condivisibile tramite parametri nell'URL.
3. README: sostituire le istruzioni Flask con `vercel dev`, con una nota su `python3` per Windows e sulla struttura reale dei file.

---

## Ordine e dipendenze

1. **Verifica della struttura dei file** (prerequisito di tutto).
2. **Fase 1** e **Fase 3**: indipendenti, si possono fare in parallelo.
3. **Fase 2**: dopo la Fase 1, così il service worker mette in cache la versione già corretta.
4. **Fase 4**: solo dopo le precedenti.

## Domande aperte

- La struttura reale del repo è quella del README (`public/`) o quella dei file allegati (radice)?
- Il comportamento di "Oggi" (punto 4) va bene così, o preferisci mantenere "Tutti" come selezione predefinita?
- Il tempo di cache di cinque minuti per le lezioni è accettabile, o preferisci un valore più basso?
