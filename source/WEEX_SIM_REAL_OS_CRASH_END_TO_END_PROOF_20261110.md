# WEEX — prova effettiva crash OS + exchange API-SIM
Data locale: 10 novembre 2026, ~00:24, Europe/Rome.
PC: DESKTOP-HFC0ULG. Directory: D:\FUNDSHOT\weex_alerts

## Dimostrazione eseguita
Un processo separato ha aperto su API-SIM WEEX una posizione ETHUSDT LONG 0.002, ISOLATED 1x, con stop nativo MARK_PRICE. Subito dopo aver ricevuto e salvato l'ACK WEEX ha eseguito un VERO os._exit(79). Il processo principale ha verificato il codice di terminazione 79, poi ha riconciliato via nuovi GET autenticati l'ordine di ingresso e lo stop, verificato la posizione esatta, eseguito **una sola** richiesta /capi/v3/closePositions in API-SIM e verificato l'ordine di chiusura e i fill reduceOnly.

### Identificativi WEEX API-SIM
- Host: https://api-sim.weex.com (non produzione).
- Client order ID: wxpilot_sim_crash_20261110_a
- Entry order ID: 814813351304495306
- Native stop algo ID: 814813351350632650
- Position ID: 814813351333855434
- Close order ID: 814813361974804682
- Child PID originale: 57508; recovery parent PID: 40208.
- Notional stimato: 4.26226 USDT, leva ISOLATED 1x (non CROSS 100x).
- Stato finale journal: SIM_CRASH_RECOVERY_FLAT_VERIFIED; exactCloseVerified=true; accountFlat=true; terminalStopVerified=true; stopStatus=CANCELED.
- Rilancio dello stesso test: ALREADY_RESERVED_NEVER_RESEND; nessun reinvio.

## Audit indipendente
Script GET-only diverso: `weex_sim_real_os_crash_independent_audit_20261110_a.py`.
- Autenticazione su API-SIM con sessione HTTP separata, zero POST.
- entryMatched=true
- closeMatched=true
- closeFillsMatched=true
- accountFlat=true; openPositions=0; openOrders=0; openAlgos=0.
- stopFoundInHistory=true; stopHistoricalStatuses=[CANCELED].
- independentProofPass=true.

## Artefatti e file sul PC
- `weex_sim_real_os_crash_recovery_20261110_a.py`: processo entry child + recovery parent, URL allowlist solo api-sim.weex.com, journal monouso.
- `weex_sim_real_os_crash_recovery_20261110_a.json`: journal autentico di prova.
- `weex_sim_real_os_crash_independent_audit_20261110_a.py`: GET-only audit indipendente.
- `weex_sim_real_os_crash_independent_audit_20261110_a.json`: risultato audit.

## Limite cruciale e stato conto vero
Questa è una prova REALMENTE eseguita sull'exchange SIMULATO con crash reale di un processo OS; NON è il crash del worker di produzione WEEX CROSS 100x, né usa tutta la stessa pipeline V5/V8 di ingresso e reduceOnly. Non vale come 10/10 del gate originale. Il test reale su conto produzione resta ancora da certificare; non modificare o inventare l'attestazione.
Conto reale autenticato: STOPPED, integrità [], posizioni 0, ordini 0, condizionali 0, unresolvedWrites []; NO_GO 9/10. Certificatore: NO_REAL_WORKER_CRASH_EVIDENCE.
Monitor Windows indipendente: heartbeat stabile PASS; exit policy reale disarmata.
Nessuna scrittura HTTP a host di produzione durante la prova.
