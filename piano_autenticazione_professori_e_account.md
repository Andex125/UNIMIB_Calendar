# 🔐 Piano Dettagliato: Autenticazione Docenti, Sicurezza e Transizione Multi-Account

> **Documento Tecnico Programmatico e Piano di Attuazione**  
> Progetto: *UNIMIB Orari & Campus Companion*  
> Data: 2026-10-20  
> Autore: Team Architettura & Sicurezza UNIMIB Calendar

---

## 📌 1. Analisi Diagnostica dello Stato Attuale

Un'analisi approfondita della codebase (backend serverless in `api/` e client SPA in `public/js/app.js` e `public/index.html`) ha evidenziato tre criticità fondamentali nel sistema di autenticazione:

### 1.1 Mancanza di Autenticazione nell'Endpoint Docenti (`api/teacher_notes.py`)
- **Problema di Sicurezza Severo**: Il metodo `do_POST` dell'endpoint `/api/teacher_notes` (utilizzato per aggiungere note a corsi/lezioni, assegnare il docente designato per la co-docenza e cancellare note) non effettuava **alcun controllo di autenticazione né di autorizzazione**.
- **Impatto**: Qualsiasi client o script non autenticato poteva inviare richieste `POST` a `/api/teacher_notes`, sovrascrivere o cancellare le note visibili agli studenti e riassegnare i docenti delle lezioni, falsificando `author_name` e `author_email` senza che il server verificasse l'identità del mittente.
- **Mancanza nel Frontend**: Nel client (`public/js/app.js`), le funzioni `saveTeacherNote()`, `deleteTeacherNote()` e `saveDesignatedTeacher()` non inviavano l'header `Authorization: Bearer <session_token>`, comunicando in modo totalmente anonimo con l'API.
- **Disallineamento Parametri e Schema Risposta**:
  - `saveDesignatedTeacher()` nel client inviava `teacher_name`, mentre il backend cercava solo `designated_teacher`.
  - `syncTeacherNotesFromApi()` nel client cercava `data.notes` e `data.designated_teachers`, mentre il backend restituiva `data.course_notes`, `data.lesson_notes` e `data.lesson_teachers`. Di conseguenza le note salvate sul server non venivano caricate correttamente al refresh.

### 1.2 Impossibilità di Passare da un Account a un Altro (Account Switching)
- **Assenza di Meccanismo Multi-Account**: Nel client, una volta effettuato l'accesso (Google o PIN), la schermata di login veniva nascosta completamente e l'unica opzione disponibile era "Esci dal profilo".
- **Logout Distruttivo della Sessione**: Cliccando su "Esci dal profilo", il client invocava `DELETE /api/profile`, revocando immediatamente il token di sessione sul server Redis. Era quindi impossibile mantenere attive più sessioni (ad esempio un account Studente e un account Docente, oppure account di colleghi/studenti diversi sullo stesso dispositivo) e passare agilmente da uno all'altro.
- **Bug Critico di Contaminazione Dati nel Cambio Account**:
  In `handleGoogleAuthCredential()` (e `handleLoginProfile()`):
  ```javascript
  if (data.config && (!state.config || !state.config.corso)) {
    state.config = data.config;
    saveConfig(state.config);
    applyConfig();
    ...
  }
  ```
  Se l'Account A aveva selezionato un corso (`state.config.corso` presente), al momento del login dell'Account B la condizione `(!state.config || !state.config.corso)` risultava **falsa**! Di conseguenza:
  1. La configurazione dell'Account B salvata nel cloud non veniva mai caricata.
  2. L'Account B visualizzava il calendario e le preferenze dell'Account A.
  3. Alla prima sincronizzazione automatica, la configurazione dell'Account A sovrascriveva il profilo dell'Account B su Redis!
- **Contaminazione Dati Docente e Corsi Esami**:
  - `PROF_ASSOCIATED_TEACHER_KEY` e `professorScheduleState.lessons` non venivano reimpostati quando si passava da un docente a un altro o da docente a studente, mostrando l'orario del docente precedente.
  - `examsState.extraCourses` subiva la medesima condizione di blocco (`!examsState.extraCourses.length`), impedendo il caricamento degli insegnamenti del nuovo account.

### 1.3 Revisione Generale del Codice di Autenticazione (`api/profile.py` e `api/_common.py`)
- Il backend gestisce correttamente token Google verificati e hash PBKDF2-HMAC-SHA256 con salt a 16 byte e rate-limiting (5 tentativi per 10 minuti).
- Tuttavia, la logica di estrazione e validazione della sessione (`session:<token>`) e dell'account (`account:<clean_nick>`) era duplicata e dispersa tra i file, senza un helper centralizzato e standardizzato in `_common.py`.
- Nei profili creati con PIN mancava la persistenza esplicita del campo `role` e di un'eventuale email istituzionale associata.

---

## 🎯 2. Obiettivi del Piano di Miglioramento

1. **Blindare `/api/teacher_notes` (OWASP A01: Broken Access Control)**:
   - Richiedere obbligatoriamente un token di sessione valido in `Authorization: Bearer <token>` per tutte le operazioni di scrittura/cancellazione (`POST`).
   - Verificare che il profilo autenticato abbia ruolo `professor` (`@unimib.it`). Utenti non autenticati ricevono `401 Unauthorized`; utenti studenti o privi di ruolo docente ricevono `403 Forbidden`.
   - Utilizzare le informazioni anagrafiche del profilo verificato (`nickname`, `email`) eliminando il rischio di identity-spoofing.
   - Allineare la risposta JSON del backend e il parsing frontend per una sincronizzazione bidirezionale perfetta.

2. **Introdurre il Supporto Multi-Account e Account Switching Fluido**:
   - Creare un gestore locale di account (`unimib_saved_accounts` in `localStorage`).
   - Quando un utente accede con Google o PIN, salvare il profilo e il token nella lista degli account registrati sul dispositivo.
   - Nel modale del Profilo, consentire sia di visualizzare l'account attivo che di passare con 1-click tra gli account salvati (es. "🎓 Mario Rossi (Studente)" ⇄ "🏛️ Prof. Mario Rossi (Docente)").
   - Aggiungere il pulsante "Accedi con un altro account" senza distruggere la sessione attuale.
   - Consentire la disconnessione del singolo account o di tutti gli account.

3. **Risolvere la Contaminazione dei Dati al Cambio Account**:
   - Al cambio account o al nuovo login, rimpiazzare sempre `state.config` e `examsState.extraCourses` con quelli propri dell'account di destinazione.
   - Resettare e ricaricare lo stato docente (`PROF_ASSOCIATED_TEACHER_KEY`, cattedra lezioni, note).
   - Invocare `updateTimetableForRole()` per commutare istantaneamente l'interfaccia (vista studente vs vista cattedra docente).

4. **Verifica Rigorosa con Test Suite e Test E2E**:
   - Aggiornare e ampliare `tests/backend/test_teacher_notes.py` per testare scenari non autenticati (401), studente (403), docente autorizzato (200).
   - Aggiungere test di coesistenza sessioni e account switching in `tests/backend/test_google_auth.py`.
   - Eseguire l'intera suite di regressione (120+ test) garantendo zero rotture.

---

## 🛠️ 3. Fasi Operative di Implementazione

### Fase 1: Backend (`api/_common.py`, `api/teacher_notes.py`, `api/profile.py`)
- [x] In `api/_common.py`: implementare helper centralizzato `get_authenticated_account(headers, body=None)` per recuperare e validare sessione e account Redis.
- [x] In `api/teacher_notes.py`:
  - Aggiungere middleware di controllo auth e ruolo `professor` in `do_POST`.
  - Bloccare richieste non autenticate con HTTP 401 e richieste non docente con HTTP 403.
  - Normalizzare la lettura parametri (`designated_teacher` / `teacher_name`).
  - Normalizzare `get_all_notes_and_assignments()` per fornire sia le chiavi legacy che le nuove chiavi (`notes`, `course_notes`, `lesson_notes`, `designated_teachers`, `lesson_teachers`).
- [x] In `api/profile.py`:
  - Assicurare che il ruolo e l'email vengano sempre preservati correttamente nelle risposte e negli aggiornamenti.

### Fase 2: Frontend (`public/js/app.js`, `public/index.html`)
- [x] Implementare storage multi-account `unimib_saved_accounts`:
  - `getSavedAccounts()`, `saveAccountToStorage()`, `removeSavedAccount()`.
- [x] Implementare funzione di transizione pulita `switchAccount(cleanNickOrShareCode)`:
  - Salva lo stato dell'account attuale prima del passaggio.
  - Carica la configurazione e gli esami dell'account di destinazione.
  - Pulisce e ricarica i dati docente se si entra/esce dal ruolo docente.
  - Aggiorna la vista e notifica con toast.
- [x] Aggiornare `handleGoogleAuthCredential()` e `handleLoginProfile()`:
  - Applicare sempre la configurazione dell'account autenticato senza blocchi da configurazioni preesistenti.
  - Registrare l'account loggato nella lista multi-account.
- [x] Aggiornare `saveTeacherNote()`, `deleteTeacherNote()`, `saveDesignatedTeacher()`:
  - Inviare l'header `Authorization: Bearer ${profileState.sessionToken}`.
  - Allineare i campi payload.
- [x] Aggiornare `syncTeacherNotesFromApi()`:
  - Riconciliare la lettura di `course_notes` / `lesson_notes` e `lesson_teachers`.
- [x] Aggiornare UI in `public/index.html` e `renderProfileModal()`:
  - Inserire sezione "I tuoi account" con selettore/switcher account salvati.
  - Pulsante "Aggiungi / Passa a un altro account".
  - Opzione per disconnettere il singolo account senza cancellarlo dal server o distruggere gli altri.

### Fase 3: Testing & Collaudo
- [x] Aggiornare i test unitari in `tests/backend/test_teacher_notes.py`.
- [x] Aggiungere test per il multi-account in `tests/backend/test_google_auth.py`.
- [x] Eseguire `python3 -m unittest discover -s tests/backend`.
- [x] Eseguire test di simulazione frontend/API end-to-end.

---

Questo piano garantisce la risoluzione definitiva sia della falla di autenticazione dei professori, sia del meccanismo di passaggio fluido tra account.
