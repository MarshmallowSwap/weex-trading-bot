# WEEX — Priorità API di protezione rispetto alla scansione (V20)
Data: 2026-11-10

## Modifiche installate
- weex_api_budget.py: quota comune SQLite, con lock transazionale.
  Per le richieste market-data GET non critiche (klines, depth,
  market trades, premiumIndex, apiTradingSymbols) è imposta
  una riserva di almeno 250 unità nella finestra >=600s
  per le API di conto, ordini, TP e recupero.
  Le chiamate autenticate critiche non sono limitate da questo
  nuovo cap ma restano soggette ai veri limiti API WEEX.
  Limiti exchange, cooldown e order limits mantenuti.
- weex_scan_data.py: massimo 80 richieste scanner/ciclo
  e stop anticipato se il contatore comune raggiunge 240/490.
  Nessun nuovo dato mercato viene fabbricato se il limite scatta.
- test_weex_recovery_api_priority_v20.py: verifiche di
  riserva e ammissione GET ad alta priorità senza rete.

## Test
- 26/26 regressioni mirate PASS incluse scanner, worker recovery,
  supervisor e governor.
- Ricertificazione build: OFFLINE_BUILD_REATTESTED,
  164 test, 83 file hash; LIVE resta STOPPED, gate NO_GO.
- Stato letto: 1 posizione, 1 ordine condizionale, 0 ordini regolari,
  nessuna scrittura locale irrisolta, gate 8/10.
- Nessun ordine inviato da questi script di diagnostica e modifica.

## Anomalia di traffico NON attribuita
- Il registro condiviso API elenca coppie di richieste
  /capi/v3/order con orders=1 e corrispondente risposta HTTP 200,
  inclusa coppia alle 2026-11-10 09:08:03 UTC.
- La presenza di POST con HTTP 200 NON certifica esecuzione
  finanziaria, ma non è mera prenotazione di quota senza rete.
  Il journal API non identifica processo/payload/clientOrderId.
- Occorre attribuire esplicitamente tali POST e verificare l'esito
  autenticato dell'exchange prima di autorizzare live.
  Nessun tentativo di alterare posizioni o ordini manuali.

## Limiti del risultato
- La riserva di 250 è una policy di ammissione delle chiamate
  pubbliche discrezionali: non garantisce che processi esterni
  o attività critiche non consumeranno in seguito quella quota.
- Il certificato fresco di riconciliazione non è stato ancora
  ottenuto. Nessuna falsificazione 9/10.
- La certificazione crash del vero worker resta assente.
