# WEEX — verifica integrata del vero worker, V22
Data: 10 novembre 2026

## Stato iniziale
- Task S4U e heartbeat verificati, supervisore OBSERVING_NOT_ARMED.
- Permesso monouso EXIT assente.
- Nessun durable UNKNOWN post-ACK del vero worker.
- Conto CROSS: posizione AINUSDT manuale e un ordine condizionale.
- STOPPED, integrity=[], release 9/10 NO_GO.

## Prove effettivamente eseguite
- 84/84 test offline PASS sui moduli di supervised worker recovery,
  monitor, independent incident supervisor, real recovery, exit policy,
  exact close readback, crash evidence, promotion e trial admission.
- Esecuzione reale di weex_live_worker.py con opzione
  --supervised-crash-recovery:
  RECOVERY_READBACK_UNCERTAIN, errorType RecoveryBlocked,
  exit code 3, ordersSent=0, entryRetries=0.
- Esecuzione di weex_supervised_worker_recovery_process_v8.py:
  NO_DURABLE_UNKNOWN_WORKER_ENTRY,
  workerRestartConfirmed=false, exchangeWrites=0, entryRetries=0.
- Check finale: STOPPED, integrity=[], 1 posizione,
  1 conditional, 0 regular orders, unresolvedWrites=[],
  release 9/10 NO_GO.

## Limiti e prerequisiti
Non è stato eseguito un vero crash dopo ACK in produzione.
I test offline non valgono come prova live 10/10.
Mancano un supervisor READY_TO_RECOVER verificato e un
permesso monouso di uscita. Una posizione manuale AINUSDT
occupa margine CROSS, impedendo un ingresso di test sicuro
con il guardian account-wide.

Per rilascio definitivo occorrono: autorizzazione indipendente
exact close, controllo margine account-wide, budget API,
durable UNKNOWN reale, restart del vero worker,
nessun duplicato, close reduceOnly e readback ETH flat.

Nessun ordine, chiusura, modifica leva o modifica AINUSDT
in questa verifica. Bot STOPPED, 9/10 NO_GO.
