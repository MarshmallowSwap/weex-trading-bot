# WEEX — Controller di pre-abilitazione recovery V24
10 novembre 2026

## Implementazione
- weex_operational_recovery_controller_v24.py: valutatore
  di pre-abilitazione locale, senza invii API o concessione di permessi.
- test_weex_operational_recovery_controller_v24.py: prove offline
  su task S4U, heartbeat, STOPPED/integrity, SDK close reduceOnly,
  permesso exit, riserva API e snapshot CROSS comprensivo di AINUSDT.
- Test v24 + regressioni v23, monitor e exit: 27/27 PASS.
- Build reattestata: 164 test, 83 file verificati.

## Osservazione operativa
- Task monitor S4U verificato: true.
- Monitor PID e heartbeat confermati: true.
- Preview SDK reduceOnly e quota API: true.
- Permesso exit monouso su produzione: false.
- Snapshot conto sufficientemente recente: false.
- Prova integrata operativa restart+exit: non attestata.
- Risultato: OPERATIONAL_PREARM_BLOCKED.
- readyToRecover=false, mayPublishReadyHeartbeat=false,
  entryAllowed=false, closeAllowed=false.
- Nessuna promozione forzata e nessuna scrittura exchange.
- Bot STOPPED, gate 9/10 NO_GO.
- AINUSDT e TP manuali invariati.

## Limite esplicito
Questo controller controlla prerequisiti, ma NON è ancora
il controller operativo con prova di recupero e uscita
sufficiente a pubblicare READY_TO_RECOVER.
La prova del crash reale dopo ACK resta non eseguita.
Non convertire il test offline in un certificato live.

## Prossimo intervento tecnico
- Dimostrare con test end-to-end reale del controller S4U
  la capacità di rilevare durable UNKNOWN, avviare il vero
  worker GET-only, consumare una volta un permit di uscita
  specifico e ottenere readback di chiusura.
- Separare il collaudo offline dal permesso di intervento live.
- Richiedere snapshot fresco account-wide e collaterale CROSS
  non impegnato prima di qualsiasi ingresso di collaudo.
