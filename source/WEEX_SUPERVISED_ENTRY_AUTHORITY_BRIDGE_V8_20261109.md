# WEEX — collegamento autorizzazione indipendente V8
Data esecuzione PC: 2026-11-09 UTC ~23:07. ROOT: D:\FUNDSHOT\weex_alerts

## Risultato
- Creato `weex_supervised_entry_authority_bridge_v8.py` e i test `test_weex_supervised_entry_authority_bridge_v8.py`.
- Collegato effettivamente `weex_live_worker.py --supervised-crash-child` -> `weex_supervised_entry_authority_bridge_v8.run_connected(ROOT)` -> `weex_supervised_crash_entry_child_v5.run_child(...)` passando entrambe le callback `external_approval` e `independent_evidence`.
- Prima dell'avvio, `ready()` richiede heartbeat supervisor con stato `READY_TO_RECOVER` e PID vivo, e una politica di uscita monouso autorizzata. In assenza rifiuta la richiesta senza generare una scrittura exchange.
- La callback `independent_evidence` esegue una nuova lettura conto, verifica che sia vuoto, verifica parametri CROSS100 e stop relativo al prezzo. L'approvazione confronta hash SHA256 dell'esatto payload, identità client, scope, freschezza 5 s, stato STOPPED, heartbeat del supervisore ed exit permit esistente.
- Eseguito `weex_live_worker.py --supervised-crash-child`: blocco atteso `SUPERVISED_CRASH_CHILD_BLOCKED:INDEPENDENT_SUPERVISOR_NOT_READY`. Zero ordini inviati.
- Aggiornato l'audit V5 affinché verifichi il percorso worker->bridge->child in luogo della precedente dipendenza da import diretto; l'audit continua a segnalare 4 blockers reali (watchdog non può chiudere da solo, doppio crash solo simulato, close richiede autorizzazione esterna, manca reale attestazione crash).
- Backup worker `weex_live_worker.pre_authority_bridge_v8.bak`.
- Rieseguita certificazione offline: **158/158 test PASS**, manifest 83 file ricertificati, `OFFLINE_BUILD_REATTESTED`.
- Rilettura autentica: STOPPED, 0 posizioni, 0 regular/conditional ordini, unresolved writes [], integrità codice []; gate 9/10 NO_GO.

## Non certificato
- Lo stato del monitor è `OBSERVING_NOT_ARMED`, NON `READY_TO_RECOVER`. La presenza del nuovo collegamento non dimostra una chiusura in caso di crash reale. Non impostare a mano i flag di heartbeat.
- Nessun permesso uscita attivo e nessun ingresso reale eseguito.
- Per passare alla prova reale occorre verificare indipendentemente la capacità di uscita e di recovery sul percorso finale, poi autorizzare l'ingresso monouso con dati autenticati. Serve prova reale completa per attestare 10/10.
