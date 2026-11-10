# WEEX — collaudo vero worker, 10 novembre 2026

## Test realmente eseguiti
- Invocato il VERO script weex_live_worker.py con
  --supervised-crash-recovery dal suo ambiente Python di produzione.
- Primo tentativo fail-closed per disallineamento integrità dopo modifica
  del modulo evidence; ricertificazione offline completata
  (161 test, 83 hash, nessun GO forzato).
- Secondo tentativo: RECOVERY_READBACK_UNCERTAIN, exit code 3,
  ordersSent=0, entryRetries=0. Il recovery orchestrator ha restituito
  NO_DURABLE_UNKNOWN_WORKER_ENTRY, exchangeWrites=0.
- S4U supervisor heartbeat LIVE, ma OBSERVING_NOT_ARMED;
  exactExitAuthorized=false; workerRestartConfirmed=false.

## Correzione verificata
- weex_real_worker_crash_evidence_gate.py: lo stato 'conto flat'
  per la certificazione del crash è ora verificato SOLTANTO
  per il simbolo target dell'ingresso reale; posizioni e TP manuali
  su altri simboli non vengono selezionati come target.
- Test: 27/27 PASS tra certificatore crash e isolation,
  inclusi AINUSDT estraneo e ordine ETH pendente.
- La guardian di nuovi ingressi CROSS resta account-wide,
  non modificata.

## Stato produzione
- Conto reale al controllo: 1 posizione, 1 ordine condizionale
  (AINUSDT manuale secondo conferma operatore); bot STOPPED.
- Gate 9/10 NO_GO, elemento mancante
  crash_restart_recovery_live_tested.
- Mancano ingresso real worker ACK -> os._exit(79), durable UNKNOWN
  indipendente, worker restart confermato dal supervisore S4U,
  reduceOnly close verificato e zero ordini ETH residui.
- Non creare eventi UNKNOWN falsi; non forzare READY_TO_RECOVER.
- Nessuna nuova posizione/ordine eseguita in questo intervento.
