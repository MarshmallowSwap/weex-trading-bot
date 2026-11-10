# WEEX — worker reale collegato al percorso di collaudo, 2026-11-09

## Intervento realmente eseguito
- Creato backup `weex_live_worker.pre_supervised_v5_20261109.bak`.
- Modificato `weex_live_worker.py`: argomento separato `--supervised-crash-child`, che richiama `weex_supervised_crash_entry_child_v5.run_child`. Non autorizza il trading normale e non crea alcun permesso a priori.
- Test CLI effettivo: `SUPERVISED_CRASH_CHILD_BLOCKED:INDEPENDENT_EXACT_APPROVAL_AND_EVIDENCE_REQUIRED`. Il child si ferma prima di qualunque GET o POST exchange se le due callback esterne non esistono.
- Test di integrazione worker, lifecycle, gate e componenti supervisione: 126/126 PASS.
- `weex_reattest_supervised_worker_offline_20261109.py`: ha rieseguito il test CLI e 126 test, verificato worker STOPPED e assenza di modifiche al gate, quindi aggiornato con prova offline `live_release_manifest.json` per 83 file di codice; backup `live_release_manifest.before_supervised_worker_20261109.json`.
- Integrità produzione controllata dopo nuova attestazione: nessun errore.
- Stato autenticato dell'exchange: posizioni 0, ordini 0, condizionali 0, scritture irrisolte 0.
- Il rapporto audit V5 NON presenta più `V5_ENTRY_NOT_WIRED_IN_PRODUCTION_WORKER`.

## Rimangono i quattro blocchi reali dell'audit V5
1. Il watchdog attuale è solo read-only e non può completare la chiusura reale senza supervisione.
2. Il drill di recupero dopo doppio crash è una simulazione, non una prova sul vero worker con ACK reale.
3. La chiusura reale richiede autorizzazione esterna legata al payload esatto; non è ancora disponibile un servizio di supervisione indipendente con heartbeat e riavvio attivi.
4. L'attestazione originale di crash reale non esiste; non è corretto fabbricarla o simulare gli ID exchange.

## Stato di rilascio
**NO_GO 9/10. Trading STOPPED. Nessun ordine reale inviato durante questo intervento.**

Il worker è ora materialmente cablato con il collaudo separato e correttamente fail-closed. Non si deve usare `--supervised-crash-child` per tentare di aggirare l'autorizzazione indipendente. Il prossimo lavoro necessario è mettere in servizio un supervisore di recupero e chiusura realmente indipendente, provarlo sul simulatore con lo stesso codice e certificare una singola prova live minimo-rischio.
