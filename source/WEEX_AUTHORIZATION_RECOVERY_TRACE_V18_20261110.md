# WEEX — Diagnosi percorso autorizzazione e recovery v18
Data: 2026-11-10
Percorso: D:\FUNDSHOT\weex_alerts

## Provenienza
- 4930 eventi del vero worker letti.
- Ultimo OPENED_PROTECTED: 2026-11-04 09:17 UTC.
- Il 06/11 il worker lavorava in DISARMED_READY, non con nuovi ingressi.
- Live control STOPPED, generation 30, changed 2026-11-06 21:51:18 UTC.
- Code integrity clean: build_errors=[].

## Refresh del release report
- Prima del refresh, il file release era scaduto:
  LIVE_RELEASE_GATE_STALE.
- Eseguito live_release_gate.py in sola lettura.
- Nuovo risultato: NO_GO 8/10, NON 9/10.
- Controlli mancanti:
  1. order_reconciliation_certified: manca certificato fresco
     (il precedente era del 2026-11-09 23:02 UTC).
  2. crash_restart_recovery_live_tested: non esiste prova di
     crash del worker dopo ACK con recupero e uscita reale.
- Il risultato startReadinessErrors passa a LIVE_RELEASE_NO_GO.
- L'ultimo worker report e DISARMED_READY, i cicli continuano;
  non e autorizzato il nuovo ingresso.

## Stato dell'esecutore crash
- supervisor_ready=False, S4U heartbeat osservante attivo ma
  non READY_TO_RECOVER, il bridge non e armato.
- exitPolicy=NO_EXIT_POLICY.
- durableUnknownEntry=False, come atteso in assenza di incidente.
- Le prove read-only di ingresso 1x e TP non certificano crash.
- La policy v16 rimane read-only, non forza READY.

## Validazione offline
- 117 test TP, recovery, Telegram, guardian e ownership: PASS.
- 31 test aggiuntivi: live control release gate, enforcement,
  supervised worker recovery, exit policy e monitor: PASS.

## Quota API e protezione
- Quota 10 minuti al controllo: 262/490 usate, 228 rimaste;
  recovery reserve 150, entry preflight + recovery 250 non
  disponibile. Evitare cicli di riconciliazione pesanti finche
  non e verificata disponibilita sufficiente e freschezza.
- Conto reale nell'ultima lettura: 1 posizione e 1 conditional
  (AINUSDT manuale per conferma operatore).
- Cross margin collateral condiviso; manual asset non puo
  essere escluso dai controlli di rischio d'ingresso.
- Nessun ordine GET-only, POST, change leverage,
  armament o close in questa diagnosi.

## Azioni proposte — non forzate
1. Tenere saldo il recovery delle posizioni di proprieta del bot
   anche quando nuovi ingressi sono STOPPED.
2. Ritestare a quota API sufficiente il set
   live_pilot_paginated_reconciliation.py ->
   reconcile_recent_fills_readonly.py ->
   weex_account_observation.observe()/position_manager_integrated.py ->
   account_reconciliation_point1.py -> live_release_gate.py,
   rispettando la freschezza di ciascuna fonte.
3. Proseguire sul controller S4U e sulla prova reale del crash
   con autorizzazione di exit e stop legato all'ingresso,
   senza modificare gli ordini AINUSDT.
4. La promozione a RUNNING non e autorizzata da questo report.

Conclusione: i componenti storici sono ancora verificati.
Il blocco attuale non e perdita di codice: e differenza
tra worker read-only funzionante e ingresso live
autorizzato mediante certificati freschi e prova crash.
