"""Telegram text fallback, using the same evidence as the status graphic."""
from agent_health import assess_agents

def status():
    result=assess_agents()
    titles={'scanner':'Scanner','trend':'Trend','momentum':'Momentum','liquidity':'Liquidita',
            'strategy':'Strategia','risk':'Controlli rischio','execution':'Esecuzione',
            'exit':'Uscite TP','positions':'Posizioni','orchestrator':'Orchestratore'}
    labels={'ENTRY_CHECKS_PENDING':'controlli completi prima dell ingresso','WAIT_API_BUDGET':'attesa budget API','WAIT_ACCOUNT_OBSERVATION':'attesa lettura conto','ON_CONFIRMED_FILL':'nuovi TP dopo il fill; TP esistenti separati','READY_ANALYSIS':'analisi pronta','READY_READ_ONLY':'pronto in sola lettura',
            'READY_SHADOW':'pronto in shadow','BLOCKED_UNITS':'book letto; unita da verificare',
            'VALIDATION_ONLY':'runner attivo: verifiche senza invio ordini','PARTIAL_COVERAGE':'book verificato solo sulle coppie abilitate ai controlli','DISABLED_BY_USER':'disabilitato su richiesta','PREVIEW_ONLY':'calcolo TP; nessun TP attivo',
            'NOT_OBSERVED':'nessun piano nel ciclo','STALE':'dati non recenti','DEGRADED':'dati incompleti',
            'MISSING':'dati assenti','STALE_OR_INCOMPLETE':'dati incompleti o non recenti',
            'STALE_OR_DEGRADED':'ciclo non aggiornato o degradato','CONFIG_UNSAFE':'configurazione da verificare'}
    lines=['WEEX AI DESK - STATO VERIFICATO','Moduli deterministici, non processi AI indipendenti.','']
    for name,record in result['modules'].items():
        lines.append(titles[name]+': '+labels.get(record['state'],record['state']))
    lines.extend(['',__import__('live_control').display(),
                  'Verifica runner e blocchi: /live_status','Aggiornato: '+result['checkedAt']])
    return '\n'.join(lines)

if __name__=='__main__':print(status())
