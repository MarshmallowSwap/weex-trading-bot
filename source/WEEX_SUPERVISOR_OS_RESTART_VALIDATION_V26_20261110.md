# WEEX — validazione supervisore indipendente V26
Data: 2026-11-10

## Stato produzione (lettura autentica, nessuna scrittura)
- Task S4U WEEX_Supervised_Incident_Noninteractive_V10: IN ESECUZIONE.
- Monitor S4U e heartbeat reali verificati.
- Worker STOPPED; integrità []; una posizione CROSS AINUSDT
  e un ordine condizionale; ordini ordinari zero.
- Gate rilascio 9/10 NO_GO: crash_restart_recovery_live_tested.
- Prearm V24: OPERATIONAL_PREARM_BLOCKED. Mancano permesso
  EXIT reale, prova operativa certificata restart+exit,
  compatibilità CROSS. API headroom non sempre verificata.

## Test integrati OS V26
- Nuovo test_weex_supervisor_os_crash_restart_v26.py.
- Usa il vero codice del monitor v6 in processo Windows isolato
  con osservatore sintetico e directory temporanea; nessun
  collegamento WEEX o autorizzazione di ordine.
- Primo tentativo test fallito per differenza tra PID del wrapper
  del virtualenv Windows e PID dell'interprete effettivo.
- Corretto avvio con sys._base_executable e ripetuti i test:
  23/23 PASS, includendo V25 (vero ramo worker,
  exit/readback simulated) e V24/V23.
- Verificato monitor OS abrupt-kill, PID non vivo, seconda istanza
  distinta, heartbeat fresco, stato OBSERVING_NOT_ARMED;
  readiness falsificata/scaduta rifiutata.
- Dopo il test, nessun processo di collaudo rimasto attivo:
  processo audit matchingTestProcesses=[].

## Cosa non dimostra
- La seconda istanza e' stata avviata dal test harness, non dal
  task scheduler di produzione: questo NON dimostra un riavvio
  automatico del Task Scheduler dopo crash del vero worker.
- Non è stato prodotto un vero durable UNKNOWN post-ACK su WEEX.
- Exit reduceOnly e readback nei test V25 sono simulati,
  senza una posizione reale del pilot.
- Il supervisore reale pubblica OBSERVING_NOT_ARMED e NON
  READY_TO_RECOVER; non è stato forzato alcun permesso.
- Il rischio del collaterale CROSS AINUSDT rimane nel veto
  degli ingressi; posizione e TP non modificati.
- Pertanto 9/10 NO_GO, live STOPPED, nessun ordine inviato.

## Passaggio tecnico residuo
Occorre certificare l'automatico riavvio del monitor dal
Task Scheduler dopo fault con attestazione del nuovo PID e
collegare una reale prova operativa di close/readback del
pilot sotto autorizzazione monouso, evitando interferenza
con la posizione AINUSDT in CROSS.
