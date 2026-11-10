# WEEX — promozione verificabile del supervisore: policy V16
Data: 10 novembre 2026

## Implementazione verificata
- weex_supervisor_promotion_policy_v16.py: valutazione offline dei prerequisiti.
- test_weex_supervisor_promotion_policy_v16.py: test fail-closed.
- 21/21 test combinati v14-v16 PASS.
- Build reattestata: 164 test del percorso offline, 83 file verificati.
- Build integrity PASS, live gate invariato.

## Distinzione necessaria delle fasi
- PRIMA DELL'INGRESSO: S4U verificato, heartbeat recente,
  integrità, serializzazione reduceOnly, riserva API,
  permesso di uscita esplicito e snapshot completo/recente.
- DOPO IL CRASH: richiedere durable UNKNOWN del vero worker,
  readback di entry+stop, worker recovery verificato e chiusura
  reduceOnly con readback e nessun ETH residuo.
- Non richiedere UNKNOWN prima di un ingresso: sarebbe circolare.
- AINUSDT manuale non viene selezionata per una chiusura ETH,
  ma occupa collaterale CROSS e blocca un nuovo test live.

## Risultati osservati
- Task S4U: PASS.
- Heartbeat: PASS.
- SDK close preview: PASS.
- Budget API: 174/490 usate; 316 disponibili nella finestra
  verificata, riserva 250 rispettata al momento del test.
- Permesso uscita v7: non presente.
- Account: 1 posizione manuale + 1 ordine condizionale.
- Nessuna prova di controller operativo abilitato a pubblicare
  READY_TO_RECOVER. Il monitor v6 pubblica OBSERVING_NOT_ARMED.

## Esito
La policy v16 NON installa un promoter operativo S4U e NON
concede READY_TO_RECOVER. È un prerequisito tecnico verificato,
non certificazione autonoma. Nessun ingresso, chiusura,
cambio leverage o permesso live è stato eseguito.
Il percorso vero di exit va verificato con test integrato separato
prima della promozione. Gate produzione: 9/10 NO_GO; STOPPED.
