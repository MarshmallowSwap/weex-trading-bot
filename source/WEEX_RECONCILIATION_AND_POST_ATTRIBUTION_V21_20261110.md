# WEEX — POST origin readback e riconciliazione V21 (10 novembre 2026)

## Prima del refresh
- Release 8/10 NO_GO: stale order reconciliation e crash worker test mancante.
- API budget 261/490, 229 disponibili al primo controllo.
- Pairs di POST /capi/v3/order locali con status HTTP 200 nel journal del governor,
  fino a 2026-11-10 09:08:03 UTC; processo responsabile NON attribuito dal journal.

## Correlazione dei POST
- weex_live_worker_events.jsonl in prossimita' degli eventi: DISARMED_READY,
  opened=0, entryAttempts=0.
- Lifecycle writes_v1: ultime righe ENTRY/TP storiche, non nuovo ingresso del worker.
- Il codice di test contiene trasporti fake/mock e API-budget reservation,
  ma non esiste un nesso di provenienza sufficientemente provato
  tra uno specifico test e ciascun POST del journal.
- Letture autenticate GET WEEX (weex_order_origin_exchange_readback_v21.py)
  mostrano 0 fills e 0 ordini nel periodo 08:00–09:15 UTC
  dentro lo storico limitato a 100 fills e 5 pagine ordini.
- Non e' prova dell'assenza universale di ogni ordine; e' prova
  negativa nello storico bounded consultato. L'origine resta NON ATTRIBUITA.
- Nessuna nuova scrittura exchange durante questa verifica.

## Riconciliazione riuscita
- Available request-weight prima del refresh: 377, dopo: 329;
  limite prudenziale 490; riserva recovery conservata.
- live_pilot_paginated_reconciliation.py:
  100 fills, 38 ordini storici, 100 corrispondenze, 0 missing;
  pagine bounded complete.
- reconcile_recent_fills_readonly.py:
  identityResolved=true; audit economico quote=INCOMPLETE
  (non dichiarato completo per assenza di righe mancanti).
- position_manager_integrated.py: una posizione AINUSDT con
  ordine condizionale, TP_COVERAGE_CERTIFIED_READ_ONLY.
- account_reconciliation_point1.py:
  OPERATIONAL_RECONCILIATION_CLEAR, 8/8 checks true,
  manualPositionsExcluded=1, no bot capacity, no unresolved intents.
- live_release_gate.py: NO_GO 9/10,
  SOLO crash_restart_recovery_live_tested=false.
- Final status: STOPPED; 1 posizione, 1 conditional, 0 regular,
  integrity=[], unresolvedWrites=[].

## Stato e limitazioni
- Non e' stato attivato il bot, concesso permesso di close,
  inviato alcun ordine o modificato AINUSDT.
- Il certificato operativo e' temporaneo; restera' necessario
  aggiornarlo per una futura abilitazione LIVE.
- Il test vero ACK -> crash -> worker recovery -> close reduceOnly
  resta da svolgere con autorizzazione e sicurezza verificate.
