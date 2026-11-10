# WEEX — confronto ultimo avvio operativo e configurazione attuale
Data analisi: 10 novembre 2026
Percorso: D:\FUNDSHOT\weex_alerts

## Evidenze certe
- Il log persistente weex_live_worker_events.jsonl contiene 4930
  eventi worker dal 24 ottobre al 10 novembre.
- Ultimo evento OPENED_PROTECTED: 2026-11-04T09:17:12.850712+00:00,
  RUNNING generation 27, nuovo trade con stato PROTECTED.
- 5 novembre: 293 tick, 215 BLOCKED_RECOVERY e 78 DISARMED_READY.
- 6 novembre: 294 tick, tutti DISARMED_READY;
  nessun evento OPENED_PROTECTED.
- 7 novembre: 288 tick DISARMED_READY.
- 8 novembre: 202 DISARMED_READY, 85 BLOCKED, 1 WAIT_API_BUDGET.
- 9 novembre: 299 DISARMED_READY, 3 WAIT_API_BUDGET, 1 BLOCKED.
- Il controllo nella ultima lettura e STOPPED, generation 30,
  changed 2026-11-06T21:51:18.974016+00:00.
- L'ultimo worker status e DISARMED_READY; si esegue il ciclo, ma
  non ha autorizzazione di ingresso.
- Non e presente un repository Git nella cartella operativa.
  Esistono backup di configurazione e manifest, ma non un
  commit verificato dell'intera build nel giorno del successo.

## Cambiamenti cronologicamente identificati
- 04/11: codice e test per adozione TP esterni, riparazione TP.
- 05/11: guardian e policy TP evolute; numerosi tick
  BLOCKED_RECOVERY prima del ripristino monitoraggio.
- 06/11: interruttore STOPPED (generation 30, sera);
  ripresa dei tick DISARMED_READY non significa nuovi trade.
- 07/11: weex_live_new_entry_guard.py rafforzato;
  veto account-wide per esposizioni CROSS, TP/SL e profili non
  certificati. Decisione 06/11 23:38 registra NO_GO.
- 09/11: live_release_gate.py aggiornato e prova crash
  9/10 NO_GO; config 100x, orderCostTargetUSDT 15, stopLoss disabled.
- 10/11: scope/ownership multi-symbol e audit/monitor
  indipendente; non e stato ripristinato il rilascio live.

## Distinguere fatti da ipotesi
- Il successo piu recente di nuovo ingresso automatico e
  documentato il 04/11, non il 06/11.
- Il motivo preciso dello STOP del 06/11 non e deducibile
  soltanto dal log worker. Non asserire che sia causato da
  un singolo gate senza prova.
- La presenza di 9/10 NO_GO non rende falsa la capacita di
  riconciliare e proteggere posizioni, ma non certifica il
  recupero autonomo da un vero crash post-ACK.

## Regressione di funzioni storiche
117/117 PASS: TP repair gate/intent/journal/preflight/request/simulator,
external TP adoption, guardian new entry, ownership multi-symbol,
position protection, worker recovery, exit policy, process monitor,
trading modes.

## Configurazione attuale verificata
Execution enabled=false, mode=PRETRADE; control STOPPED.
Risk CROSS, minimumLeverage=100, initialMarginTargetUSDT=5,
orderCostTargetUSDT=15, stopLoss disabled,
maxConcurrentPositions=1, fixed TP 30 USDT gross in config.
Conto: 1 posizione + 1 ordine condizionale manuale AINUSDT
(come dichiarato dall'operatore).
Release 9/10 NO_GO, blocco crash_restart_recovery_live_tested.

## Percorso di recupero non distruttivo
1. Conservare una copia dell'attuale configurazione,
   manifest e journal PRIMA di ogni migrazione futura.
2. Mantenere TP recovery, protezione del proprio ordine,
   lock e deduplicazione; nessun rollback indiscriminato.
3. Mantenere il veto account-wide degli ingressi CROSS.
4. Gestire il normale stato di monitoring/riconciliazione
   indipendentemente dal certificato del crash test.
5. Testare process restart + read-only no duplicate con
   namespace e database isolati, poi autorizzazioni e
   collaudo protetto con riserva API e permessi verificati.
6. Nessun RUNNING, modifica leva, ordine o permesso
   di chiusura reale in questa analisi.

Conclusione: il worker storico funziona come componente di
riconciliazione; il ripristino del suo LIVE non e un
semplice rollback del gate, perche la nuova protezione
crash e la gestione del collaterale CROSS non sono ancora
certificate per un ingresso reale sicuro.
