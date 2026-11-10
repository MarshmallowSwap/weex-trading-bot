# WEEX — consolidamento recupero worker e chiusura emergenza
Data: 10 novembre 2026, Europe/Rome. PC: DESKTOP-HFC0ULG.
Root: D:\FUNDSHOT\weex_alerts

## Correzioni applicate sul percorso reale
1. `weex_supervised_worker_recovery_process_v8.py`: prima di riavviare il worker GET-only, il supervisore verifica l'esatta identità `CLIENT_ID`, symbol ETHUSDT, quantità 0.001 e gli ID numerici di ingresso, posizione e stop. Incertezza => blocco senza nuovo processo e senza ordini.
2. `weex_supervised_process_monitor_v6.py`: la chiusura d'emergenza monouso è ora indipendente dal successo del riavvio del worker; deve comunque essere verificata una singola posizione protetta tramite watchdog + doppio GET + proposta exact reduceOnly e un permesso esplicito non consumato, mentre il trasporto ri-verifica tutto prima del POST e non ritenta dopo esiti incerti. Il fallimento del riavvio non deve impedire una chiusura di sicurezza. Senza permesso non avviene POST.
3. `weex_supervised_process_monitor_v6.py`: heartbeat in thread indipendente, aggiornato anche durante GET lenti o riavvio worker; file atomico per thread per evitare collisioni. Rimane sempre OBSERVING_NOT_ARMED finché manca la certificazione reale.
4. `test_weex_supervised_worker_recovery_process_v8.py` e `test_weex_supervised_process_monitor_v6.py`: test contro identità errate, reale processo OS separato, prenotazione persistente NO_RETRY, uscita anche se il restart fallisce con permesso esplicito, blocco senza permesso, heartbeat durante lettura bloccata.
5. `weex_reattest_supervised_worker_offline_20261109.py`: ricertificazione con 161 test PASS, 83 hash integri. Task schedulato `WEEX_Supervised_Incident_Readonly_V6` riavviato. Probe heartbeat PASS. Nessuna modifica del gate di rilascio.
6. `weex_supervised_real_account_pretrade_dryrun_v9.py`: GET autentici e DB SQLite temporaneo, senza alcun invio. Preflight attualmente bloccato da `RECOVERY_API_HEADROOM_REQUIRED`, soglia non abbassata; `weex_api_budget_pressure_readonly_v9.py` mostra 287 REQUEST_WEIGHT/600 s (108 klines, 50 fills, 50 posizioni e altri), nessun nuovo ordine reale. Questo utilizzo rotante va valutato prima di un ingresso pilot.

## NUOVA PROVA WEEX API-SIM: stessa forma di ordine di chiusura della produzione
Script `weex_sim_exact_reduceonly_crash_recovery_20261110_b.py`
- Host allowlist: **https://api-sim.weex.com**. Le credenziali produzione NON sono usate.
- Ingresso: ETHUSDT LONG 0.002, ISOLATED 1x, stop nativo MARK_PRICE.
- Child process ottiene ACK da API-SIM e muore con vero `os._exit(79)`; parent di recupero nuovo verifica entry/stop con nuove GET.
- **Chiusura: POST /capi/v3/order MARKET SELL reduceOnly True, quantity 0.002**. Stesso metodo, endpoint e tipo d'ordine del trasporto di recupero produzione, invece del precedente POST /closePositions.
- Entry order ID: 814820115567608010
- Stop algo ID: 814820115605356746
- Position ID: 814820115588579530
- Close order ID: 814820126103699658
- Stato finale: `SIM_CRASH_RECOVERY_FLAT_VERIFIED`, `exactCloseVerified:true`, `accountFlat:true`, `terminalStopVerified:true`, stop storico CANCELED, 1 close, 0 duplicati.
- Script indipendente GET-only `weex_sim_exact_reduceonly_crash_independent_audit_20261110_b.py` ha confermato con altra sessione autenticata: `entryMatched:true`, `closeMatched:true`, `closeFillsMatched:true`, `accountFlat:true`, `stopFoundInHistory:true`, `independentProofPass:true`.
- File prova: `weex_sim_exact_reduceonly_crash_recovery_20261110_b.json`.
- File audit: `weex_sim_exact_reduceonly_crash_independent_audit_20261110_b.json`.

## Stato produzione — niente falsi PASS
- Account live 0 posizioni, 0 ordini e 0 ordini condizionati; bot STOPPED, build integrity PASS.
- Supervisore PID reale attivo, heartbeat PASS, ma **exit permit non attivo** e status `OBSERVING_NOT_ARMED`.
- Certificatore `weex_real_worker_crash_evidence_gate.py`: `NO_REAL_WORKER_CRASH_EVIDENCE`.
- Gate rilascio **9/10 NO_GO**. Non è stato inviato alcun ordine reale nel presente intervento.
- Il test SIM, seppure con lo stesso endpoint di uscita, non dimostra ancora il crash del vero `weex_live_worker.py` su API di produzione. Pertanto nessuna attestazione di crash live viene fabbricata e la produzione non è avviata.

Conclusione: sono stati risolti due difetti di architettura e il percorso di uscita esatto è validato sull'API-SIM con audit indipendente. La certificazione della prova con posizione vera resta ancora da svolgere.
