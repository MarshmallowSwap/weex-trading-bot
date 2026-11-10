# WEEX — collaudo finale supervisionato prima del rilascio
Data: 2026-11-09
Stato verificato: BOT STOPPED, execution.enabled=false, posizioni=0, ordini=0, condizionali=0, gate NO_GO 9/10.

## Scopo
Verificare il requisito `crash_restart_recovery_live_tested` per il **worker automatico reale**, non per l'esecutore di test indipendente. Un ordine già concluso o una simulazione non bastano.

## Condizioni prima del test
- Conferma esplicita e nuova dell'ordine reale di collaudo e dei limiti; nessuna autorizzazione precedente va riutilizzata.
- Esecuzione supervisionata dall'operatore su WEEX, mediante ambiente di test/produzione approvato per il test di failure injection.
- Account senza posizioni né ordini estranei; stesso simbolo e modalità margine verificati in lettura.
- Procedura pronta di chiusura manuale d'emergenza, stop exchange-side già collegato all'ingresso e verificabile.
- Durabilità transazionale dell'intento e identificativo clientOrderId stabile prima della richiesta HTTP.
- Interrompere solo il processo del collaudo, **mai** il monitoraggio delle posizioni o la protezione già presente sull'exchange.

## Evidenze indispensabili per il PASS
1. Intento d'ingresso scritto e sincronizzato su disco prima del POST; unico clientOrderId.
2. Evidenza indipendente che la richiesta è arrivata a WEEX, poi interruzione controllata realmente verificata durante la finestra di invio/ACK.
3. Nuovo processo: nessun secondo POST di ingresso per l'intento sconosciuto.
4. Ricerca dello stesso clientOrderId in storico WEEX con ordine e fill effettivi.
5. Lettura account con posizione e stop nativo associato: simbolo, verso, quantità, positionId, reduceOnly e trigger corrispondono.
6. Chiusura una sola volta tramite positionId, oppure piano di uscita supervisionato verificato con esito finale.
7. GET indipendenti: conto senza posizioni, ordini regolari o condizionali residui; stop in stato terminale; commissioni/fill riconciliati.
8. Registro durevole completo con timestamp e ID prova; recovery dopo nuovo riavvio senza scritture duplicate.
9. Gate ricalcolato **senza modifiche manuali ai risultati**; attivazione del worker solo tramite il percorso autorizzativo esistente e un successivo assenso esplicito.

## NO_GO immediato
- ACK perduto senza prove complete dell'esito; posizione non protetta; disallineamento di ID o quantità; chiusura incerta; qualsiasi duplicato; API non raggiungibile; compromissione del manifest; nuovo ordine non autorizzato.

## Stato delle prove attuali
- Pilota reale ETHUSDT CROSS 1x e chiusura con stop: PASS per il singolo ciclo.
- Contabilità WEEX nella finestra dei 1.335 movimenti: PASS; non implica copertura di tutta la storia.
- Crash/restart simulati: PASS.
- Crash durante il POST reale del **worker automatico**: NON ESEGUITO / NON CERTIFICATO.
- Trading automatico: STOPPED; nessuna autorizzazione al rilascio.
