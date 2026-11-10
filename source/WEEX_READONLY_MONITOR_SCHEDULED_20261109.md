# WEEX — Monitor indipendente operativo, 9 novembre 2026

## Modifiche realmente applicate
- Creato `weex_supervised_process_monitor_v6.py`: controlla il supervisore incidenti V6 e, soltanto quando trova un ingresso verificato come protetto, richiama `weex_supervised_recovery_orchestrator_v6.prepare` per costruire una proposta di uscita. Nessun invio di ordini.
- Il file di heartbeat `weex_supervised_crash_supervisor_health.json` indica volutamente `OBSERVING_NOT_ARMED`, `supportsExactReduceOnlyClose=false`, `hasIndependentRestartTask=false`. Non è una falsa attestazione READY_TO_RECOVER.
- Creato `run_weex_supervised_monitor_v6.cmd`.
- Installata attività Windows `WEEX_Supervised_Incident_Readonly_V6`, ogni minuto con l'utente corrente. Avvio manuale verificato, risultato attività 0. All'accesso Windows, controllare che il task sia attivo; si tratta di polling e non di un supervisore di trading.
- Test del monitor e componenti V6: 27/27 PASS; verificati heartbeat sempre disarmato e planner chiamato solo con posizione e stop verificati.

## Verifica remota effettuata
- API-SIM GET autenticati aggiornati: entry e close order IDs corrispondenti, fill di uscita e reduceOnly verificati, stop storico CANCELED, posizioni/ordini/stop aperti 0, audit read-only PASS.
- Ultima lettura conto di produzione: posizioni 0, ordini 0, condizionali 0, unresolvedWrites [].
- Worker produzione integrità PASS, modalità STOPPED, gate 9/10 NO_GO.

## Lavoro NON completato
- Monitor osserva e propone, ma non può ancora eseguire in autonomia una chiusura real-exchange né ripristinare il worker dopo un crash.
- `weex_supervised_crash_entry_child_v5.run_child` necessita ancora di callback esterne indipendenti per autorizzazione ed evidenze; senza di esse si arresta prima della rete.
- Necessaria prova finale reale con identità ordini e posizione verificate, stop nativo confermato, crash del worker, riconciliazione indipendente, chiusura senza duplicati e account completamente flat.
- Solo il certificatore originario con prove vere può rilasciare 10/10.

## Esito
Nessun ordine reale inviato. **NO_GO 9/10, bot STOPPED**. La nuova attività pianificata è un monitor di sicurezza, non una riattivazione del trading.

## Comando gestione task
`schtasks.exe /Query /TN WEEX_Supervised_Incident_Readonly_V6 /V /FO LIST`
`schtasks.exe /End /TN WEEX_Supervised_Incident_Readonly_V6`
`schtasks.exe /Change /TN WEEX_Supervised_Incident_Readonly_V6 /Disable`

## Addendum: freschezza preflight, 23:21 Italia
- Ricostruita l'intera catena di attestazione operativa con GET autenticati: `weex_final_live_status_readonly_20261109.py`, `position_manager_integrated.py`, `live_pilot_paginated_reconciliation.py`, `reconcile_recent_fills_readonly.py` e `account_reconciliation_point1.py`.
- `OPERATIONAL_RECONCILIATION_CLEAR`, 8/8 check PASS; 100 trade recenti associati, 0 order IDs mancanti. La riconciliazione economica estesa resta `INCOMPLETE`: il risultato non certifica tutta la storia.
- `weex_supervised_crash_executor_v2.py --read-only-preflight`: `READ_ONLY_CHECKS_PASS_REAL_ADAPTER_NOT_AUTHORIZED`, ETHUSDT 0.001, CROSS 100x, nozionale indicativo 2.12681 USDT e stop nativo previsto 2120.42; nessun ordine inviato.
- Nuovi GET autenticati su API-SIM: precedente entry/exit/stop confermati, conto simulato flat, stop storico cancellato.
- Task Windows ricontrollato dopo un'esecuzione periodica autonoma alle 23:21 locali: ultimo esito `0`, prossima esecuzione alle 23:22.
- Certificatore reale: `NO_REAL_WORKER_CRASH_EVIDENCE`; rilascio 9/10 NO_GO, bot STOPPED, conto reale flat. Non dichiarare GO né trasformare il monitor di sola lettura in prova di gestione di una chiusura reale.
