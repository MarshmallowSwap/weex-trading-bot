"""Opening cost configuration only. Never submits or modifies exchange orders."""
import json
import os
import re
from decimal import Decimal
from pathlib import Path

CONFIG = Path(__file__).with_name('weex_ai_risk_config.json')
MODE = 'COST_INCLUDING_ENTRY_FEE'


def validate_cost(raw):
    value = str(raw).strip().replace(',', '.')
    if len(value) > 40 or not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', value):
        raise ValueError('Usa un importo positivo con massimo 2 decimali, es. 7,50.')
    amount = Decimal(value)
    if amount <= 0:
        raise ValueError('Il costo deve essere almeno 0,01 USDT.')
    return amount


def save_cost(raw):
    amount = validate_cost(raw)
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    # Update only the budget; execution, stop loss, leverage and existing trades are untouched.
    config['risk']['entryBudgetMode'] = MODE
    config['risk']['orderCostTargetUSDT'] = format(amount, 'f')
    temp = CONFIG.with_suffix('.cost.tmp')
    temp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, CONFIG)
    return amount


def message():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    risk = config['risk']
    amount = Decimal(str(risk.get('orderCostTargetUSDT', '5')))
    return (f'💰 Costo per apertura: {amount:.2f} USDT (SUSDT in demo).\n'
            'Include margine + commissione di ingresso; non è il controvalore con leva.\n'
            'Invia un importo positivo, anche con virgola, es. 7,50.\n'
            'Vale per i nuovi ingressi. Quantità minima, saldo e limiti exchange restano verificati.\n'
            '/cancel per annullare. Nessun ordine viene aperto da questa impostazione.')


def begin(conn, chat):
    conn.execute("INSERT INTO input_state VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET mode=excluded.mode",
                 (chat, 'await_custom_cost'))
    conn.commit()
    return message()


def accept(conn, chat, raw):
    amount = save_cost(raw)
    conn.execute('DELETE FROM input_state WHERE chat_id=?', (chat,))
    conn.commit()
    return (f'✅ Costo per nuova apertura: {amount:.2f} USDT (SUSDT in demo), '
            'margine + commissione di ingresso inclusi. Posizioni esistenti invariate. Nessun ordine inviato.')
