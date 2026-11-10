# WEEX — integrazione controller recovery V25
Data: 2026-11-10

## Implementazione effettiva
- test_weex_real_worker_recovery_subprocess_v25.py:
  esegue il VERO codice weex_live_worker.py nel ramo
  --supervised-crash-recovery dentro un processo OS indipendente.
  Le funzioni lettura exchange e controllo live sono intercettate
  nel processo figlio con prove sintetiche; nessun GET/POST WEEX.
  La recovery v8 conserva il vincolo durable one-shot e non ritenta.
- test_weex_supervisor_exit_callchain_v25.py:
  esercita i veri moduli exit_policy v7 e recovery_orchestrator v6
  con un trasporto simulato: consumo permit una sola volta,
  readback di flat simulato e fallback fail-closed.
- weex_integrated_recovery_controller_v25.py:
  raggruppa il test di processo e quello di uscita,
  il veto CROSS v23 e il preflight operativo V24.
  Nessun permesso reale o modifica della modalità LIVE.

## Verifiche
- 32/32 regressioni combinate PASS.
- 21/21 test dell'esecutore integrato V25 PASS.
- Stato del controller:
  ISOLATED_REAL_WORKER_AND_EXIT_CHAIN_DRILL_PASS_NO_LIVE_CERTIFICATION.
- Prearm produzione OPERATIONAL_PREARM_BLOCKED.
  Il task S4U e monitor heartbeat risultano verificati.
  Mancano: permesso EXIT reale, snapshot CROSS fresco e
  attestazione completa di crash post ACK + recovery/exit live.
- Conto letto: STOPPED, integrity=[], una posizione AINUSDT
  con conditional TP e nessun ordine ordinario,
  unresolvedWrites=[], release 9/10 NO_GO.

## Confini di sicurezza
- La prova del ramo vero worker NON è un incidente reale:
  read_exchange è stato sostituito nel processo figlio.
- Il readback di chiusura è simulato; il trasporto esterno non
  ha inoltrato un close a WEEX.
- Nessun ordine e nessuna cancellazione; AINUSDT non modificata.
- Nessun READY_TO_RECOVER pubblicato; i prerequisiti operativi
  devono essere dimostrati PRIMA di armare qualsiasi ingresso.
- Il gate crash_restart_recovery_live_tested rimane falso.

## Ulteriore passaggio
Eseguire il collaudo real-money solo in presenza di:
  conto CROSS libero da esposizione incompatibile,
  permit exit indipendente con consenso operatore,
  S4U recovery affidabile e verifica fresh dell'API budget;
  quindi vero post-ACK crash e readback + chiusura di
  un'esposizione del solo pilot, senza retry.
