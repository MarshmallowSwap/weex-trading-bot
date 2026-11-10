# WEEX — riconciliazione fresca e riserva API, 10 novembre 2026

## Obiettivo
Aggiornare il certificato operativo della riconciliazione e quindi
ricontrollare il release gate, SENZA ordini e senza compromettere
la riserva per il recupero di posizioni in CROSS.

## Verifica
- Ultimo gate verificato prima del tentativo: 8/10 NO_GO;
  order_reconciliation_certified e crash_restart_recovery_live_tested
  non superati.
- Controllo reale: STOPPED, una posizione e un ordine condizionale,
  nessun ordine ordinario e nessuna scrittura non risolta.
- WEEX API budget: 257/490 al primo controllo, 233 disponibili.
  Durante la prova: 279/490, 211 disponibili.
- Lo script di refresh v19 richiede 330 unità disponibili
  prima di partire (150 riserva emergenza + budget diagnosi).
- La soglia non è stata raggiunta nella finestra limitata.
- Risultato v19: DEFERRED, BUDGET_HEADROOM_BELOW_SAFE_RESERVE,
  steps=[], exchangeWrites=0. Non è stata rigenerata una falsa
  certificazione; AINUSDT non è stata modificata.

## Cause del consumo API viste nel journal (10 minuti)
- market/klines: 108 richieste, peso 108.
- market/depth: 37 richieste, peso 37.
- userTrades: 10 richieste, peso 50.
- position/allPosition: 3 richieste, peso 30.
- altri endpoint: peso 37.
- Picchi klines e depth 08:53 UTC nel journal;
  i log non provano quale processo ne sia l'autore.
- La fotografia degli ultimi 60 s includeva solo un userTrades,
  peso 5; il consumo elevato e stato un burst passato e resta
  nella finestra rolling 600 s finché non scade.

## Script installati
- weex_safe_reconciliation_refresh_v19.py:
  controlla le riserve e prova il percorso GET-only
  (trade history, matching fills, posizioni/protezioni,
  certificato operativo, report release).
- weex_api_callers_readonly_v19.py:
  analisi locale per endpoint del journal API.
- Nessun nuovo ingresso, chiusura, permesso o cambio di stato.

## Conclusione
La riconciliazione non è stata completata per mancanza di
quota nella finestra; la precedente certificazione è scaduta.
Il motivo del rilascio 8/10 non è stato aggirato.
La guardia reale di ammissione LIVE resta NO_GO.
