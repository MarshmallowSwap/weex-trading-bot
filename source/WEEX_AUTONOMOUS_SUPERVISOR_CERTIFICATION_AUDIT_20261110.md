# WEEX — audit autonomia supervisore e permessi — 10 novembre 2026
Progetto: D:\FUNDSHOT\weex_alerts

## Esito, non equivalente al GO
L'attività pianificata originale WEEX_Supervised_Incident_Readonly_V6
usa LogonType=InteractiveToken. Il recupero autonomo del monitor
dopo kill del processo è stato dimostrato (PID 10040 -> 21524, ~59 s),
ma la sopravvivenza a logout/riavvio Windows non è stata dimostrata.
Il tentativo di creare una nuova task di prova con LogonType=S4U,
senza toccare la task originale, è fallito con CimException;
la sessione corrente non è elevata.
Script di prova separato per amministratore:
weex_s4u_readonly_probe_20261110.ps1
Non sostituisce la task originale, rimuove la task temporanea e
non invia ordini.

## Modifiche sicurezza eseguite
weex_supervised_entry_authority_bridge_v8.py:
- serializzazione SDK delle richieste di ingresso (con stop nativo)
  e uscita MARKET reduceOnly, entrambe offline;
- verifica reale budget WEEX tramite require_supervised_recovery_headroom;
- evidenza esplicita che stop live e fill live non sono ancora provati;
- consenso negato se manca prova SDK o budget.

Test: 33 mirati PASS.
Test OS monouso (weex_exit_permit_os_process_drill_v10.py):
primo sottoprocesso consuma un singolo permesso in SQLite temporaneo;
secondo sottoprocesso riceve consumed=false. PASS.
Nessuna autorizzazione di produzione concessa, zero write exchange.

Build: 161 test offline PASS, 83 file hash/integrità PASS.
Conto reale dopo test: STOPPED, flat 0 posizioni/ordini/algos,
0 unresolved writes. Gate: 9/10 NO_GO.
Certificatore reale: NO_REAL_WORKER_CRASH_EVIDENCE.

## Requisiti residui prima del test live
1. Configurare e provare task non interattiva con identità OS autorizzata,
   privilegi minimi e accesso effettivo a file/WEEX, senza sessione utente;
   eseguire la prova OS logout solo con accesso alternativo affidabile.
2. Produrre attestazione indipendente dell'effettivo percorso di recupero
   e uscita monouso: non inferire capacità da flag hardcoded.
3. Verificare budget prima e al momento dell'ordine, protezione stop live,
   e solo dopo effettuare prova controllata sul vero worker con
   registrazione ACK, crash, restart, GET indipendenti e chiusura.
Non modificare READY_TO_RECOVER manualmente.
