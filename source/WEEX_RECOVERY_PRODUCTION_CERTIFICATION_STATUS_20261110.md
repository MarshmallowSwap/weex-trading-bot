# WEEX — certificazione del percorso di crash, 10 novembre 2026

## Stato produzione
**NO_GO 9/10.** Nessun rilascio live, nessun ordine di prova reale.
Lettura autenticata account: modo STOPPED, posizioni 0, ordini 0,
algos 0, unresolved writes 0. Supervisore non interattivo S4U
attivo; monitor heartbeat valido, ma OBSERVING_NOT_ARMED.
Permesso di chiusura in produzione: NO_EXIT_POLICY.
Certificato crash del vero worker: NO_REAL_WORKER_CRASH_EVIDENCE.

## Evidenze positive
- Test sistema operativo Windows: monitor S4U si riavvia dopo
  terminazione forzata (PID 17084 -> 19636) senza fallback manuale.
- Autenticazione simulatore https://api-sim.weex.com, audit separato:
  entryOrderId 814820115567608010,
  closeOrderId 814820126103699658,
  stopAlgoId 814820115605356746.
  entryMatched=true, closeMatched=true, closeFillsMatched=true,
  accountFlat=true, stopHistoricalStatuses=[CANCELED],
  independentProofPass=true. Il test non modifica produzione.
- 38 test software monitor/recovery/exit/readback PASS.
- Permesso monouso provato offline in due processi Windows distinti,
  con database temporaneo; secondo consumo negato.

## Condizioni ancora non soddisfatte
1. La task S4U riavvia il *supervisore*. Il monitor, nel ramo di recovery,
   sa lanciare il vero worker in modalità GET-only solo se trova
   un durable UNKNOWN preciso e prova exchange dell'ordine protetto.
   Non è ancora stata verificata questa condizione col conto reale.
2. L'heartbeat dichiara correttamente
   supportsExactReduceOnlyClose=false,
   hasIndependentRestartTask=false,
   closeDispatchAllowed=false, entryDispatchAllowed=false.
   Non è lecito convertirli manualmente a true.
3. Il permesso live di uscita monouso non esiste e non è stato concesso.
   Non va creato prima di avere il percorso di exit indipendente pronto.
4. Ultima finestra API controllata: weight 254/490 con riserva
   di recupero 150 e riserva preflight 100; 254+250>490.
5. Non esiste certificato reale di crash ACK->restart->close->flat.

## Conclusione
Il percorso offline/simulato è verificato, il riavvio OS del monitor
è verificato. L'affidabilità operativa dell'uscita su real money
NON è certificata. Mantieni STOPPED/NO_GO; non forzare READY_TO_RECOVER.
