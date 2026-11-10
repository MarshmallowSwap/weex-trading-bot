# WEEX — verifica indipendente V14 (10 novembre 2026)

## File installati e verificati
- weex_independent_recovery_capability_v14.py
- test_weex_independent_recovery_capability_v14.py
- weex_independent_recovery_capability_v14_latest.json
- weex_v14_final_readonly_audit.ps1

## Evidenze
- Task S4U non interattivo: PASS
- Heartbeat del supervisore vivo: PASS
- Configurazione STOPPED e integrità: PASS
- Serializzazione SDK MARKET reduceOnly ETH: PASS (zero HTTP POST)
- Permesso monouso di uscita: NON PRESENTE
- Intent ENTRY con stato durable UNKNOWN del vero worker: NON PRESENTE
- Headroom API preflight+recovery: NON VERIFICATO
- 51 test dedicati a recupero, exit policy, close readback,
  crash evidence e capability audit: PASS
- Ricertificazione offline successiva: 164 test, 83 file hashed, PASS
- weex_live_worker.py --supervised-crash-recovery:
  RECOVERY_READBACK_UNCERTAIN, exit 3, ordersSent=0, entryRetries=0
- weex_supervised_worker_recovery_process_v8.py:
  NO_DURABLE_UNKNOWN_WORKER_ENTRY, exchangeWrites=0
- Ultima lettura conto: STOPPED, 1 posizione e 1 conditional
  (AINUSDT manuale, non toccata), 0 ordini ordinari.

## Conclusione
CAPABILITY AUDIT PASS per task/heartbeat/serialization; test del
true worker recovery correttamente fail-closed in assenza di un reale
ingresso interrompibile. Non c'e prova autentica ACK -> crash
-> supervised recovery -> reduceOnly close -> ETH flat.
Il monitor resta OBSERVING_NOT_ARMED e il release gate 9/10 NO_GO.
Nessun permesso live creato, nessun ordine reale inviato,
nessuna configurazione di rilascio forzata.
