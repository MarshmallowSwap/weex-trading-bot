# WEEX — recupero dell'uscita dopo ACK perduto (2026-11-09)

## Nuove integrazioni realizzate
- `weex_supervised_exact_close_readback_v6.py`: verifica separatamente l'ordine di chiusura `reduceOnly`, i fill, quantità, identità, stop in stato terminale e posizioni/ordini/condizionali tutti vuoti.
- Aggiunti `resolve_close_order_id` e `recover_lost_close_ack`: quando l'ACK del close è perduto, il recupero cerca nei GET di storico il `newClientOrderId` immutabile del close. Accetta esclusivamente un unico ordine corrispondente al payload durabile, senza un nuovo POST.
- `weex_supervised_recovery_orchestrator_v6.py`: dopo un ACK di chiusura non considera il solo ACK sufficiente; chiama il verificatore autenticato GET e produce `CLOSE_VERIFIED_BY_INDEPENDENT_GET` solo in caso di prove coerenti. Qualunque incertezza lascia `safeToRetryClose=false`.
- `weex_supervised_process_monitor_v6.py`: ad ogni ciclo schedulato, in presenza di un close `OUTCOME_UNKNOWN` nel database, esegue riconciliazione soltanto GET usando il client ID esatto, senza ripetere la chiusura. Il monitor resta sempre `OBSERVING_NOT_ARMED`.
- Aggiornati test `test_weex_supervised_exact_close_readback_v6.py`, `test_weex_supervised_recovery_orchestrator_v6.py`, `test_weex_supervised_process_monitor_v6.py`. **45/45 PASS** nei test mirati, inclusi scenari duplicato, ID errato, stop aperto, conto non vuoto, fill mancanti e incertezza.

## Stato reale dell'installazione
- Task Windows `WEEX_Supervised_Incident_Readonly_V6` abilitato ogni minuto, ultima esecuzione ore 23:32 con codice 0.
- Conto WEEX produzione: posizioni 0; ordini 0; condizionali 0; unresolvedWrites [].
- Manifest integrità produzione: nessun errore; bot STOPPED; gate 9/10 NO_GO.
- Certificatore crash: `NO_REAL_WORKER_CRASH_EVIDENCE`. Non è stata prodotta artificiosamente nessuna attestazione e non è stato inviato alcun ordine reale.

## Limitazioni sostanziali
- Queste modifiche sono la riconciliazione post-close e dopo ACK perduto, NON un supervisore che può autorizzare il pilota, verificare un reale crash e disporre automaticamente chiusure.
- Il collaudo finale su worker reale con ingresso/stop, crash e recupero non è stato ancora completato. Un test offline non lo sostituisce.
- CROSS 100x resta rischioso; nessun bypass del gate o riarmo è stato effettuato.
