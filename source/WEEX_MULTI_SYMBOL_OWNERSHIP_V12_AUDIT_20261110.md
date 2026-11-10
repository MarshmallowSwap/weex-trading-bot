# WEEX — Ownership multi-symbol v12, 10 novembre 2026

## Implementato
- weex_multi_symbol_ownership_v12.py: audit read-only derivato da
  weex_user_live_lifecycle.sqlite3, con prove ENTRY persistenti e
  corrispondenza esatta positionId + symbol.
- Classifica BOT_AUTOMATIC, BOT_TELEGRAM, UNATTRIBUTED e CONFLICT.
  Non attribuisce automaticamente al bot posizioni prive di prove,
  e non confonde operazioni manuali da app con comandi Telegram.
- weex_live_worker.py: capacity() include ownershipAudit nel report
  senza usarlo per autorizzare nuovi ingressi.
- Mantiene weex_live_new_entry_guard.py: il veto per posizioni e
  ordini esistenti in modalità CROSS resta applicato al conto intero.
- Le chiusure ETH restano soggette a posizione/stop/ID exact match
  del supervisore v11; non vengono applicate a simboli estranei.

## Test e stato
- 7 test ownership v12 PASS.
- 48 test mirati ownership / supervisor / worker PASS.
- 21 test guardian CROSS e protezioni, inclusi ownership, PASS.
- Ricertificazione offline: 161 test, 83 file; NO LIVE GO.
- Conto: mode STOPPED, 1 posizione, 1 ordine condizionale,
  0 ordini ordinari, 0 scritture non risolte.
- Nessun exchange POST, nessuna modifica alla posizione manuale.

## Limiti
- Il registro è derivato dal giornale persistente del worker,
  non è una prova esaustiva dell'origine di ogni ordine exchange.
  Le posizioni senza prova restano UNATTRIBUTED, non autorizzate
  alla gestione da parte del worker.
- La separazione non abilita ingressi CROSS con esposizioni esterne.
  L'account share collateral continua a imporre veto per nuovi ingressi.
- La certificazione di crash del vero worker resta 9/10 NO_GO.
