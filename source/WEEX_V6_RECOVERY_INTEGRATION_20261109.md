# WEEX — integrazione recupero V6 / verifica rilascio — 2026-11-09

## Consegna verificata
- Installato `weex_supervised_recovery_orchestrator_v6.py`: prepara **solo** una proposta di chiusura reduceOnly dopo doppia verifica coerente del conto e dello stop. Nessun POST, nessun consenso automatico, nessuna modifica a release gate o configurazioni di produzione.
- Installato `test_weex_supervised_recovery_orchestrator_v6.py`: controlli su id mismatched, stop mancante, conto non flat, modalità attiva, lettura fallita, preview non valida, hash del payload.
- Suite mirata: **72/72 PASS**.
- Ultimo stato autenticato del conto: **zero posizioni, zero ordini e zero ordini condizionati**, nessuna scrittura irrisolta; integrità produzione senza errori.
- Orchestratore: `NO_SUPERVISED_UNKNOWN_ENTRY`, nessuna transazione da recuperare.
- Bot automatico **STOPPED**, certificazione indipendente **9/10 NO_GO**. Nessun ordine reale in questa sessione.

## Blocchi ancora reali
1. La V5 del pilota non è ancora connessa al percorso di invio del worker di produzione; il file originale e il suo hash di integrità non sono stati toccati.
2. Il supervisore V6 è un componente di sola lettura e non un servizio indipendente di riavvio permanente con chiusura automaticamente verificata su WEEX.
3. La prova su API-SIM già salvata usa un percorso diverso dall'orchestrazione definitiva V5/V6.
4. La prova di crash reale del worker e la certificazione indipendente del conseguente recupero sono assenti.
5. La leva CROSS 100x aumenta il rischio di liquidazione prima che un stop possa essere eseguito. Non è una prova senza rischio.

## Decisione
Non forzare `GO` né cambiare manualmente manifest/certificatore. Prima della riattivazione servono integrazione verificata del worker, supervisore realmente indipendente con recupero del processo e della chiusura, test end-to-end sullo stesso codice in API-SIM, e prova live a esposizione minima autorizzata e attestata dall'exchange.
