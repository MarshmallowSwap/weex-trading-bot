# WEEX — separazione recupero ETH / esposizioni manuali, 10 novembre 2026

## Implementazione verificata
- Nuovo modulo weex_supervised_ownership_scope_v11.py:
  classifica snapshot exchange completo per simbolo target ETHUSDT;
  conserva elenco di esposizioni e ordini estranei per audit.
- weex_independent_incident_supervisor_v6.py:
  confronto posizione e stop sull'unico ETHUSDT; ordini di altri
  simboli non vengono confusi con l'ordine del collaudo.
- weex_supervised_reduce_only_close_plan_v4.py:
  planning MARKET reduceOnly applicato solo all'ETHUSDT proveniente
  dal proof indipendente con positionId e stopAlgoId esatti.
- Test regressione: 65/65 PASS.
- Lettura reale API GET-only: una posizione AINUSDT e un ordine
  condizionale AINUSDT, nessuna posizione/ordine ETHUSDT.
  Nessuna scrittura exchange e nessuna modifica al bot.

## Limiti espliciti
La separazione in questo intervento riguarda il recovery/close ETH
del collaudo, NON una autorizzazione generalizzata a nuovi ingressi.
L'etichetta 'manuale' proviene dalla conferma dell'operatore;
il solo simbolo non dimostra la provenienza di ogni ordine.
Per il normale bot multi-symbol resta necessario applicare un
registro di proprietà persistente per ordine e posizione, e
gestire il rischio di collaterale condiviso in CROSS. Un'altra
posizione ETHUSDT manuale o un ordine ETH addizionale blocca
ancora correttamente il recupero pilota.

## Release
Prod mode STOPPED, 9/10 NO_GO.
Supervisore non interattivo online ma ripristino reale del worker
e uscita reale autonomi non certificati. Nessun GO forzato.
