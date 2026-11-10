# WEEX — intervento concreto sul blocco di collaudo — 2026-11-09

## Correzioni implementate
1. `weex_supervised_crash_entry_child_v5.py`: aggiunto `liveAuthorizationScope=SCOPE` nel piano pilota. Senza questo campo, `weex_live_worker.Gateway.validate` rifiuta `LIVE_SCOPE_REQUIRED` prima della spedizione; si tratta di un mismatch di integrazione reale, non di un generico test non passato.
2. `weex_supervised_recovery_orchestrator_v6.py`: aggiunto `dispatch_approved_close`, che combina doppia verifica del conto, digest SHA256 del payload esatto, identità dell'ordine/posizione/stop e il trasporto monouso già disponibile in `weex_supervised_reduceonly_close_transport_v4.py`. Non è esposto da CLI; senza approvazione esterna non invia ordini.
3. `test_weex_supervised_gateway_scope_v5.py` creato; estesi `test_weex_supervised_recovery_orchestrator_v6.py` e casi negativi di modifica quantità/ID ordine/ID stop/operazione.
4. Test mirati: 77/77 PASS (offline).

## Verifiche del conto reale
- Trading STOPPED.
- Posizioni: 0; ordini regolari: 0; ordini condizionati: 0; unresolvedWrites: [].
- Integrità codice di produzione: senza errori.
- Gate: 9/10 NO_GO, ultimo requisito `crash_restart_recovery_live_tested`.

## Condizioni reali ancora mancanti
- Integrazione della CLI del child V5 nel file di produzione `weex_live_worker.py` con manifest aggiornato in modo autenticabile.
- Supervisore separato di riavvio con heartbeat effettivo, verifica indipendente e possibilità di chiusura sicura; l'attuale V6 fornisce verifica e proposta ma non un servizio di recupero autonomo permanente.
- Prova sul simulatore degli stessi percorsi operativi completi, inclusi restart e chiusura; successivamente un pilot reale minimo, chiuso e certificato da attestazioni autentiche.
- Il certificatore indipendente deve produrre 10/10 GO. Non alterarne la soglia né inventare attestazioni o ordini.

**Conclusione operativa:** il difetto di scope è corretto e il percorso di chiusura è meglio integrato; nessun ordine reale è stato inviato. NON è possibile dichiarare 10/10 con le prove disponibili. Il bot resta STOPPED.
