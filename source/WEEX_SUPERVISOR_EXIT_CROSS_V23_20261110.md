# WEEX — test incrociato supervisore, EXIT e CROSS — V23
Data 2026-11-10.

## Cosa è stato effettivamente eseguito
- Nuovo test file test_weex_supervisor_exit_cross_integration_v23.py.
- Processo OS indipendente di weex_supervised_process_monitor_v6.run()
  con osservatore sintetico, database temporaneo separato.
- Monitor heartbeat scritto e verificato; status OBSERVING_NOT_ARMED.
- Il monitor NON pubblica READY_TO_RECOVER con il codice corrente.
- Exit policy v7 su SQLite temporaneo: grant simulato con
  operator_authorized=True SOLO in test offline, consumo esatto
  una volta; prove reduceOnly non valide respinte; doppio consume
  negato. Nessun permesso concesso in produzione.
- Incident sintetico con piano di close: senza permit, exit executor
  non invocato. Nessun ordine.
- Snapshot CROSS simulato con posizione/TP AINUSDT: veto pre-entry
  SHARED_CROSS_COLLATERAL_NOT_FLAT confermato.
- Anche snapshot vuoto e capability flags favorevoli NON autorizzano
  READY_TO_RECOVER senza controller operativo attestato.
- 35/35 test PASS (nuovi test integrati + regressioni
  monitor, exit policy, promozione e admission).

## Stato produzione letto
- STOPPED, integrity=[].
- 1 posizione, 1 ordine condizionale, 0 ordini regolari.
- Release 9/10 NO_GO, blocker crash_restart_recovery_live_tested.
- Supervisore attivo in OBSERVING_NOT_ARMED;
  permesso monouso exit sul conto reale assente.
- Nessun ordine, chiusura o concessione permit reale.

## Limiti
La promozione a READY_TO_RECOVER non è stata eseguita;
l'integrazione è ancora un esercizio offline con incident sintetico.
Non esiste prova del vero worker sotto crash post ACK con posizione
protetta in produzione; il gate non deve essere aggiornato a 10/10.
Posizione AINUSDT manuale non modificata, collaterale CROSS occupato.
