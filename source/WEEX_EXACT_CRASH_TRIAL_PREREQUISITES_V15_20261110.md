# WEEX — prerequisiti collaudo reale, 10 novembre 2026

## Controlli eseguiti
- Audit S4U v14: task, heartbeat, integrita, serializzazione
  reduceOnly PASS; permesso monouso exit MANCANTE.
- Budget API 600s: weightUsed=280 su limite 490, rimangono 210.
  Preflight 100 + riserva recovery 150 = 250, quindi NO_GO.
- Ultima verifica live: modo STOPPED, 1 posizione manuale
  AINUSDT + 1 ordine condizionale, 0 ordini ordinari,
  0 unresolved writes.
- Stato monitor hard-coded OBSERVING_NOT_ARMED; il worker
  richiede READY_TO_RECOVER. Non esiste ancora percorso provato
  che consenta la promozione. Non alterare flags arbitrariamente.
- Exit policy v7: NO_EXIT_POLICY; serve un permesso monouso
  rilasciato da azione specifica e distinta, non dal monitor.
- Ancora assente durable UNKNOWN del vero worker dopo HTTP ACK.

## Implementazione
- weex_exact_crash_trial_admission_v15.py: veto fail-closed
  indipendente, non effettua GET/POST, non concede permessi,
  non abilita bot. Blocca anche esposizioni CROSS manuali quando
  osservate con snapshot fresco.
- test_weex_exact_crash_trial_admission_v15.py: 8 test PASS;
  uniti con audit v14: 13/13 PASS.
- In questa esecuzione la cache account era scaduta:
  FRESH_ACCOUNT_SNAPSHOT_MISSING; non effettuati GET extra
  per non consumare il budget di recovery già insufficiente.

## Stato
Certificazione 9/10 NO_GO, trading STOPPED.
Nessuna nuova posizione, nessun ordine exchange, nessuna modifica
alla posizione AINUSDT, nessun permesso live creato.
