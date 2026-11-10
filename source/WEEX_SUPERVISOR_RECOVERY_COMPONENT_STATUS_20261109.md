# WEEX — stato integrazione supervisore e recupero reale
Data: 2026-11-09. PC: DESKTOP-HFC0ULG. Progetto: D:\FUNDSHOT\weex_alerts

## Componenti concretamente integrati
1. `weex_live_worker.py`: entrypoint separato `--supervised-crash-child` (in assenza di approvazione indipendente blocca prima del network), e `--supervised-crash-recovery` GET-only, per nuovo processo reale senza reinviare l'ingresso.
2. `weex_supervised_crash_entry_child_v5.py`: eliminato il falso `capacity={count:0}`; ora nuova lettura conto e `account_capacity()` effettiva prima del confine di invio; `supervisor_ready()` usa Windows OpenProcess/GetExitCodeProcess, non `psutil` non installato.
3. `weex_supervised_independent_coordinator_v7.py`: esercizio con due vere morti OS dei child (79 e 81), due nuovi processi di ripresa, due journal durabili, entrata/close duplicate impedite. Exchange della prova SIMULATO: zero HTTP.
4. `weex_supervised_worker_recovery_process_v8.py`: un solo nuovo processo `weex_live_worker.py --supervised-crash-recovery` per ingresso reale `UNKNOWN` già protetto e indipendentemente riscontrato; prenotazione SQLite pre-spawn e blocco rigoroso di replay; valida ID di entry, posizione e stop con proof autonoma.
5. `weex_supervised_exit_policy_v7.py`: politica pre-autorizzabile di una sola chiusura ETHUSDT SELL MARKET reduceOnly 0.001, specifico clientOrderId, scadenza, consumo irreversibile prima del POST. Nessun permesso attivo sul conto di produzione ora; nessun ingresso mai autorizzato da questo modulo.
6. `weex_supervised_recovery_orchestrator_v6.py`: doppia lettura indipendente, piano exact close, digest payload, trasporto monouso v4 e readback finale di ordine/fill/stop/conto vuoto, con NO RETRY dopo outcome ambiguo.
7. `weex_supervised_exact_close_readback_v6.py`: recupero dopo perdita dell'ACK d'uscita tramite clientOrderId immutabile da storico exchange, senza inviare una seconda chiusura.
8. `weex_supervised_process_monitor_v6.py`: pipeline reale di monitoraggio: watchdog -> preview protetta -> avvio una sola volta del worker GET-only dopo UNKNOWN -> politica exit-only -> eventuale reduceOnly unico -> riconciliazione no retry. Rimane conservativamente `OBSERVING_NOT_ARMED` fino a certificazione reale.

## Installazione e verifica Windows
- Attività schedulata `WEEX_Supervised_Incident_Readonly_V6` resta abilitata, script aggiornato in `run_weex_supervised_monitor_v6.cmd` per loop ogni 3 secondi. XML dell'attività originale salvato. Scheduler `MultipleInstancesPolicy=IgnoreNew`; le occorrenze successive non lanciano una seconda istanza.
- La creazione di una nuova attività ONLOGON è stata rifiutata da Windows (Accesso negato), quindi è stata riutilizzata quella già autorizzata. Il precedente script è conservato come `run_weex_supervised_monitor_v6.before_continuous.cmd`.
- Probe effettivo heartbeat PASS: PID indipendente stabile fra due letture a distanza di sette secondi, heartbeat avanzato e nessuna autorizzazione di apertura.
- Suite integrata: **154 test su 154 PASS**. Manifest offline ricertificato con 83 hash dei file protetti: `OFFLINE_BUILD_REATTESTED`.
- Drill con crash OS: **INDEPENDENT_OS_PROCESS_RESTART_SIM_PASS**, entrambe le riprese in processo distinto e duplicati zero.

## Stato reale verificato
- Conto di produzione: posizioni 0, ordini regolari 0, ordini condizionati 0, unresolvedWrites [].
- Worker e strategia: **STOPPED**. Build integri.
- Politica exit-only: `NO_EXIT_POLICY` (non esiste un'autorizzazione monouso attiva).
- Comando del worker `--supervised-crash-child`: `INDEPENDENT_EXACT_APPROVAL_AND_EVIDENCE_REQUIRED` — bloccato prima dell'ordine.
- Certificatore originario: `NO_REAL_WORKER_CRASH_EVIDENCE`.
- Rilascio: **9/10 NO_GO**. Nessun ordine reale emesso in questo intervento.

## Limiti che non posso certificare come completati
- Non è collegato l'IPC/ticket dell'approvazione indipendente esatta per L'INGRESSO del pilota V5: il comando di test non può ancora creare ordini autorizzati in produzione.
- L'uscita reale monouso è pronta nel codice e collegata, ma non è stata verificata mediante lo stesso percorso su un caso di reale worker-ACK crash WEEX; non chiamarla `READY_TO_RECOVER` prima della prova.
- Manca osservare l'effettivo processo di produzione terminato con codice 79 dopo ACK WEEX, recuperare con il nuovo worker, liquidare la sola posizione pilot, verificare lo storico dei fill e lo stop terminale, e far attestare il risultato dall'originario `weex_real_worker_crash_evidence_gate.py`.
- Nessun bypass del normale gate e nessuna certificazione artificiale sono stati eseguiti.

Conclusione: codice recupero+uscita e supervisione continua migliorati e verificati offline; 10/10 reale non ancora ottenuto.
