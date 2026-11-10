"""Button navigation and durable, authenticated input wizards. No exchange writes.

Manual confirmation delegates to the existing guarded manual entry handler.
Every wizard mutation is revision-bound, expires and is consumed before dispatch.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def button(text, data):
    return {'text': text, 'callback_data': data}


def keyboard(*rows):
    return {'inline_keyboard': list(rows)}


def nav(back='aimenu:home'):
    return [button('⬅ Indietro', back), button('🏠 Menu', 'aimenu:home')]


def home():
    return keyboard([button('📈 Trading', 'aimenu:trade')],
                    [button('📊 Posizioni e risultati', 'aimenu:monitor')],
                    [button('⚙ Impostazioni', 'desk:settings')],
                    [button('🔧 Stato e recupero', 'desk:recovery')],
                    [button('❔ Guida', 'desk:help')])


def trading():
    return keyboard([button('✋ Apri posizione manuale', 'desk:manual')],
                    [button('🧭 Modalità ingressi', 'tradingmode:show')],
                    [button('▶ Prepara avvio LIVE', 'livectl:start')],
                    [button('⏹ Ferma nuovi ingressi', 'livectl:stop')],
                    [button('📡 Stato LIVE', 'livectl:status')], nav())


def monitoring():
    return keyboard([button('📂 Aperte', 'positionreport:open'), button('✅ Chiuse 24h', 'positionreport:closed')],
                    [button('PnL recente', 'desk:pnl'), button('Win rate eseguiti', 'desk:winrate')],
                    [button('🔎 Coppie candidate', 'aimenu:candidates')], nav())


def settings():
    return keyboard([button('💰 Costo ingresso', 'aimenu:cost'), button('🟢 TP lordo USDT', 'desk:tp_gross')],
                    [button('📊 Limite posizioni automatiche', 'aimenu:positions')],
                    [button('🛑 Stop Loss', 'aimenu:sl')],
                    [button('🧮 Modelli di calcolo', 'desk:models')],
                    [button('📋 Scheda impostazioni', 'desk:card')], nav())


def recovery():
    return keyboard([button('📡 Stato LIVE', 'livectl:status'), button('🤖 Stato servizi', 'aimenu:agents')],
                    [button('🔎 Blocchi e soluzioni', 'livectl:blocks')],
                    [button('🔄 Riconcilia posizioni', 'livectl:reconcile')],
                    [button('🔧 Risolvi un simbolo', 'desk:resolve')],
                    [button('🎯 Verifica TP', 'desk:tp_check'), button('Proposte recupero TP', 'desk:tp_repair')],
                    [button('🧪 Verifica avvio · nessun ordine', 'livectl:test_once')], nav())


def blocks_keyboard(root):
    rows=[]
    path=Path(root)/'weex_user_live_lifecycle.sqlite3'
    if path.exists():
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as c:
            symbols=[r[0] for r in c.execute("SELECT DISTINCT symbol FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED','PROTECTED') ORDER BY symbol LIMIT 12")]
        rows=[[button('Verifica '+s, 'desk:pick:resolve:'+s)] for s in symbols]
    return keyboard(*rows, [button('🔄 Riconcilia tutto', 'livectl:reconcile')],
                    [button('Altro simbolo / ID ordine', 'desk:resolve')], nav('desk:recovery'))


def decorate(result, root):
    """Give existing replies a route forward without changing their execution logic."""
    if not result or not result.get('reply'):
        return result
    reply = result['reply']
    markup = reply.setdefault('reply_markup', keyboard())
    rows = markup['inline_keyboard']
    if not rows:
        rows.extend([[button('📈 Trading', 'aimenu:trade'), button('🔧 Stato e recupero', 'desk:recovery')]])
    if not any(b.get('callback_data') == 'aimenu:home' for row in rows for b in row):
        rows.append([button('🏠 Menu', 'aimenu:home')])
    return result


def _connect(root):
    c = sqlite3.connect(Path(root) / 'telegram_button_menu.sqlite3', timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA synchronous=FULL')
    c.execute('''CREATE TABLE IF NOT EXISTS wizard_v1(
        token TEXT PRIMARY KEY, chat TEXT, user TEXT, revision INTEGER,
        expires REAL, payload TEXT, used INTEGER DEFAULT 0)''')
    c.commit()
    return c


def _invalidate(root, chat, user):
    with closing(_connect(root)) as c, c:
        c.execute('UPDATE wizard_v1 SET used=1 WHERE chat=? AND user=?', (chat, user))


def _new(root, chat, user, payload):
    token = secrets.token_hex(6)
    with closing(_connect(root)) as c, c:
        c.execute('DELETE FROM wizard_v1 WHERE expires<?', (time.time()-86400,))
        c.execute('UPDATE wizard_v1 SET used=1 WHERE chat=? AND user=?', (chat, user))
        c.execute('INSERT INTO wizard_v1 VALUES(?,?,?,0,?,?,0)',
                  (token, chat, user, time.time()+600, json.dumps(payload)))
    return token, 0, payload


def _symbols(root):
    from weex_trading_modes import normalize_symbol
    try:
        raw = json.loads((Path(root)/'universe_latest.json').read_text(encoding='utf-8'))
        symbols = sorted({normalize_symbol(x['symbol']) for x in raw['symbols']})
        if symbols:
            return symbols
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'TAOUSDT']


def symbol_page(root, purpose, page=0):
    symbols = _symbols(root)
    pages = (len(symbols)+11)//12
    page = max(0, min(page, pages-1))
    buttons = [button(s.removesuffix('USDT'), 'desk:pick:'+purpose+':'+s) for s in symbols[page*12:(page+1)*12]]
    rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    arrows = []
    if page:
        arrows.append(button('◀ Precedenti', f'desk:symbols:{purpose}:{page-1}'))
    if page+1 < pages:
        arrows.append(button('Successive ▶', f'desk:symbols:{purpose}:{page+1}'))
    if arrows:
        rows.append(arrows)
    rows.extend([[button('⌨ Componi simbolo', 'desk:type:'+purpose)], nav('aimenu:trade' if purpose=='manual' else 'desk:recovery')])
    return f'Scegli il simbolo · pagina {page+1}/{pages}.\nElenco locale; disponibilità e limiti saranno verificati prima dell’ordine.', keyboard(*rows)


def _fingerprint(root):
    import live_control
    from weex_trading_modes import get_mode
    cfg, digest = live_control.configuration(root)
    s = live_control.state(root)
    value = [digest, s['mode'], s['generation'], get_mode(root)['mode']]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest(), cfg


def render(token, revision, payload):
    prefix = f'desk:w:{token}:{revision}:'
    kind = payload['kind']
    if kind == 'side':
        return (f"Apertura manuale · {payload['symbol']}\nScegli la direzione. Segue un riepilogo da confermare.",
                keyboard([button('🟢 LONG', prefix+'LONG'), button('🔴 SHORT', prefix+'SHORT')], nav('desk:manual')))
    if kind == 'confirm':
        return payload['preview'], keyboard([button('CONFERMO APERTURA REALE', prefix+'send')],
                                           [button('Annulla', 'desk:cancel')])
    value = payload.get('value', '')
    label = {'tp':'Obiettivo TP lordo in USDT', 'cost':'Costo ingresso in USDT · margine + commissione',
             'symbol':'Simbolo, con o senza USDT', 'ids':'ID degli ordini di chiusura · fino a 5'}[kind]
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' if kind == 'symbol' else '123456789'
    width = 6 if kind == 'symbol' else 3
    rows = [[button(ch, prefix+ch) for ch in chars[i:i+width]] for i in range(0, len(chars), width)]
    if kind != 'symbol':
        rows.append([button('0', prefix+'0'), button('Prossimo ID' if kind=='ids' else ',', prefix+('sep' if kind=='ids' else '.'))])
    rows.extend([[button('⌫ Cancella cifra', prefix+'del'), button('Svuota', prefix+'clear')],
                 [button('Continua' if kind in ('symbol','ids') else 'Salva importo', prefix+'ok')],
                 [button('Annulla', 'desk:cancel')]])
    return label+'\n\n'+(value or '—')+'\n\nUsa il tastierino qui sotto.', keyboard(*rows)


def _save_amount(root, kind, value):
    from telegram_ai_settings import validate
    from telegram_cost_settings import validate_cost
    amount = validate(value) if kind=='tp' else validate_cost(value)
    path = Path(root)/'weex_ai_risk_config.json'
    cfg = json.loads(path.read_text(encoding='utf-8'))
    if kind=='tp':
        cfg['telegramSettings']['fixedProfit'].update(enabled=True, targetNetProfitUSDT=float(amount))
        strategy=cfg.setdefault('strategySettings', {})
        strategy['targetNetProfitUSDT'] = float(amount)
        strategy['tpMode'] = 'fixed'
        strategy['tpAccountingMode'] = 'GROSS_BEFORE_COSTS'
        cfg['telegramSettings']['fixedProfit']['reference']='gross_price_pnl_before_entry_exit_fees_slippage_and_funding'
    else:
        cfg['risk'].update(entryBudgetMode='COST_INCLUDING_ENTRY_FEE', orderCostTargetUSDT=format(amount, 'f'))
    temp = path.with_suffix('.button.tmp')
    temp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)
    return amount


def _resolve_view(root, symbol):
    from weex_reconcile import diagnostics
    return diagnostics(root, symbol), keyboard(
        [button('🔄 Ricostruisci '+symbol, 'livectl:resolve:'+symbol)],
        [button('⌨ Indica ID ordine di chiusura', 'desk:ids:'+symbol)], nav('desk:recovery'))


def handle(update, cfg, root):
    cb = update.get('callback_query')
    m = ((cb or {}).get('message') if cb else update.get('message')) or {}
    sender = (cb or m).get('from') or {}
    data = str(cb.get('data', '')) if cb else str(m.get('text', '')).strip().split(' ')[0].split('@')[0].lower()
    aliases = {'aimenu:cost':'cost', 'aitpmode:amount':'tp', 'desk:tp_gross':'tp', 'aitp:custom':'tp', 'aitp:show':'tp', '/cost':'cost'}
    handled = data.startswith('desk:') or data in aliases or data in ('/menu','/start','/help','/cancel')
    if not handled:
        # Leaving a wizard, particularly STOP, makes its confirm button obsolete.
        if cb and data.startswith(('aimenu:', 'livectl:', 'tradingmode:', 'positionreport:', 'aitpmode:', 'aipos:', 'aisl:')):
            if _authorized(m, sender, cfg):
                _invalidate(root, str(m['chat']['id']), str(sender['id']))
        return None
    if not _authorized(m, sender, cfg):
        return {'handled':True, 'reply':None}
    chat, user = str(m['chat']['id']), str(sender['id'])

    def reply(text, markup=None, **extra):
        return {'handled':True, 'buttonUI':True,
                'reply':{'chat_id':chat, 'text':text, 'reply_markup':markup or home()}, **extra}

    def new(payload):
        return reply(*render(*_new(root, chat, user, payload)))

    def selected(purpose, symbol):
        from weex_trading_modes import normalize_symbol
        symbol = normalize_symbol(symbol)
        if purpose=='manual':
            return new({'kind':'side', 'symbol':symbol})
        if purpose=='resolve':
            _invalidate(root, chat, user)
            return reply(*_resolve_view(root, symbol))
        raise ValueError('Percorso non valido.')

    try:
        if data in ('/menu','/start','/help','/cancel','desk:cancel'):
            _invalidate(root, chat, user)
            from telegram_ai_fullmenu import home_text
            return reply(('Operazione annullata.\n\n' if data in ('/cancel','desk:cancel') else '')+home_text(), clearInput=True)
        if data in aliases:
            return new({'kind':aliases[data], 'value':''})
        if data=='desk:settings':
            _invalidate(root, chat, user)
            from telegram_ai_fullmenu import summary
            return reply(summary(), settings())
        if data=='desk:recovery':
            _invalidate(root, chat, user)
            return reply('Stato e recupero\n\nSe l’avvio è bloccato: leggi Stato LIVE, apri Blocchi e soluzioni e avvia Riconcilia.\nLa riconciliazione ferma i nuovi ingressi. Al termine usa Trading → Prepara avvio LIVE.', recovery())
        if data=='desk:help':
            return reply('Guida ai bottoni\n\n'
                'Trading → scegli la modalità, prepara l’avvio e conferma. Ferma nuovi ingressi lascia attivi i TP esistenti.\n\n'
                'Apertura manuale → simbolo → LONG/SHORT → riepilogo → conferma. Richiede LIVE attivo e modalità Solo manuale o Automatico + manuale.\n\n'
                'Impostazioni → costo, obiettivo TP e limite automatico. Gli importi si inseriscono con il tastierino. Le modifiche valgono per i nuovi ingressi.\n\n'
                'TP fisso lordo: obiettivo in USDT prima di fee, slippage e funding. TP netto + trailing: si attiva al prezzo del TP impostato e segue il movimento; il profitto finale può essere inferiore all’obiettivo.\n\n'
                'Posizioni e risultati → aperte, chiuse 24h e statistiche.\n\n'
                'Stato e recupero → controlli, riconciliazione e risoluzione per simbolo. Se manca un ordine di chiusura puoi indicarne l’ID con il tastierino. I controlli incompleti restano bloccanti.\n\n'
                'I vecchi comandi rimangono disponibili. Apri Menu → Apri menu per tornare qui.')
        if data=='desk:models':
            return reply('Modelli di calcolo\n\nDinamico AI, percentuale e ibrido AI sono modelli teorici: selezionarli non abilita il trading LIVE. I TP eseguibili sono Fisso lordo e Netto + trailing WEEX.',
                         keyboard([button('Dinamico AI · calcolo', 'aitpmode:dynamic')],
                                  [button('Percentuale · calcolo', 'aitpmode:percent')],
                                  [button('Ibrido AI · calcolo', 'aitpmode:hybrid')],
                                  [button('Modelli SL · calcolo', 'desk:slmodels')], nav('desk:settings')))
        if data=='desk:slmodels':
            from telegram_ai_fullmenu import sl_calculation_menu
            return reply('Stop Loss · modelli di calcolo\nNessuno di questi modelli inserisce uno stop reale. SL operativo OFF.', sl_calculation_menu())
        if data in ('desk:manual', 'desk:resolve'):
            purpose = data.split(':')[1]
            if purpose=='manual':
                import live_control
                from weex_trading_modes import get_mode
                if get_mode(root)['mode'] not in ('manual_only','automatic_manual') or live_control.state(root)['mode']!='RUNNING':
                    return reply('Per aprire manualmente scegli Solo manuale o Automatico + manuale, poi prepara e conferma l’avvio LIVE.', trading())
            _invalidate(root, chat, user)
            return reply(*symbol_page(root, purpose))
        if data.startswith('desk:symbols:'):
            _, _, purpose, page = data.split(':')
            if purpose not in ('manual','resolve'):raise ValueError('Percorso non valido.')
            _invalidate(root, chat, user)
            return reply(*symbol_page(root, purpose, int(page)))
        if data.startswith('desk:pick:'):
            _, _, purpose, symbol = data.split(':')
            return selected(purpose, symbol)
        if data.startswith('desk:type:'):
            purpose = data.split(':')[2]
            if purpose not in ('manual','resolve'):raise ValueError('Percorso non valido.')
            return new({'kind':'symbol', 'purpose':purpose, 'value':''})
        if data.startswith('desk:ids:'):
            from weex_trading_modes import normalize_symbol
            return new({'kind':'ids', 'symbol':normalize_symbol(data.split(':')[2]), 'value':''})
        if data in ('desk:pnl','desk:winrate','desk:card','desk:tp_check','desk:tp_repair'):
            return {'handled':True, 'buttonUI':True, 'reply':None, 'menuAction':data.split(':')[1]}
        if not data.startswith('desk:w:'):
            return reply('Pulsante non riconosciuto. Riapri il menu.')
        _, _, token, revision, action = data.split(':')
        follow = None
        with closing(_connect(root)) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM wizard_v1 WHERE token=? AND chat=? AND user=?', (token, chat, user)).fetchone()
            if not row or row['used'] or row['expires']<time.time():
                c.rollback()
                return reply('Pulsante scaduto o già utilizzato. Riapri il percorso dal menu; nessun ordine ripetuto.')
            if row['revision']!=int(revision):
                c.rollback()
                text, markup=render(row['token'],row['revision'],json.loads(row['payload']))
                return reply('Tocco già gestito. Continua dal tastierino aggiornato.\n\n'+text, markup)
            payload = json.loads(row['payload'])
            kind = payload['kind']
            expires = row['expires']
            used = 0
            if kind=='side' and action in ('LONG','SHORT'):
                fingerprint, config = _fingerprint(root)
                from weex_trailing import description
                payload.update(kind='confirm', side=action, fingerprint=fingerprint,
                    preview=f"APERTURA SU FONDI REALI\n{payload['symbol']} {action}\n"
                    f"Costo: {config['risk']['orderCostTargetUSDT']} USDT (margine + commissione)\n"
                    +description(config['strategySettings'])+
                    f"\nLeva massima disponibile, minimo {config['risk'].get('minimumLeverage',100)}×; Cross; SL OFF.\n"
                    'Quantità e disponibilità saranno verificate prima dell’invio.\nConferma entro 2 minuti.')
                expires = time.time()+120
            elif kind=='confirm' and action=='send':
                used = 1
                if _fingerprint(root)[0] != payload['fingerprint']:
                    follow = ('changed', payload)
                else:
                    follow = ('manual', payload)
            elif kind in ('tp','cost','symbol','ids'):
                value = payload.get('value','')
                if action=='del':value=value[:-1]
                elif action=='clear':value=''
                elif action=='ok':
                    if kind in ('tp','cost'):
                        from telegram_ai_settings import validate
                        from telegram_cost_settings import validate_cost
                        (validate if kind=='tp' else validate_cost)(value)
                    elif kind=='symbol':
                        from weex_trading_modes import normalize_symbol
                        normalize_symbol(value)
                    else:
                        ids=value.split()
                        if not 1<=len(ids)<=5 or any(not x.isascii() or not x.isdigit() or len(x)>20 for x in ids):
                            raise ValueError('Inserisci da 1 a 5 ID numerici, massimo 20 cifre ciascuno.')
                    used=1
                    follow=(kind, payload)
                elif len(action)==1 and action in ('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' if kind=='symbol' else '0123456789.'):
                    if action=='.' and (kind=='ids' or '.' in value):raise ValueError('Separatore non valido.')
                    value+=action
                elif action=='sep' and kind=='ids':value=value.rstrip()+' '
                else:raise ValueError('Pulsante non valido per questo inserimento.')
                if len(value)>(104 if kind=='ids' else 30):raise ValueError('Valore troppo lungo. Cancella una cifra.')
                payload['value']=value
            else:raise ValueError('Pulsante non valido per questa operazione.')
            revision = int(revision)+1
            c.execute('UPDATE wizard_v1 SET payload=?, revision=?, used=?, expires=? WHERE token=?',
                      (json.dumps(payload), revision, used, expires, token))
            c.commit()
        if follow:
            kind, payload = follow
            if kind=='changed':return reply('Impostazioni, modalità o stato LIVE cambiati. Riapri la posizione manuale e controlla il nuovo riepilogo.', trading())
            if kind=='symbol':return selected(payload['purpose'], payload['value'])
            if kind in ('tp','cost'):
                import live_control
                live_control.stop(user, chat, root)
                amount = _save_amount(root, kind, payload['value'])
                return reply(f"✅ {'TP lordo' if kind=='tp' else 'Costo ingresso'}: {amount:.2f} USDT.\n"
                             'Vale per i nuovi ingressi; posizioni esistenti invariate. Ingressi fermati: prepara e conferma l’avvio per usare la nuova impostazione.',
                             keyboard([button('▶ Prepara avvio LIVE', 'livectl:start')], nav('desk:settings')))
            from telegram_live_control import handle as live_handle
            text = (payload['symbol']+' '+payload['side'] if kind=='manual' else
                    '/risolvi '+payload['symbol']+' '+payload['value'])
            synthetic = {'message':{'chat':{'id':chat}, 'from':{'id':user}, 'text':text, 'date':int(time.time())}}
            return decorate(live_handle(synthetic, cfg, root), root)
        return reply(*render(token, revision, payload))
    except (ValueError, KeyError, TypeError) as exc:
        # Keep the valid editor usable after input errors; its transaction rolled back.
        if data.startswith('desk:w:'):
            try:
                with closing(_connect(root)) as c:
                    row=c.execute('SELECT * FROM wizard_v1 WHERE token=? AND chat=? AND user=? AND used=0', (data.split(':')[2],chat,user)).fetchone()
                if row and row['expires']>=time.time():
                    text, markup=render(row['token'],row['revision'],json.loads(row['payload']))
                    return reply(str(exc)+'\n\n'+text, markup)
            except (ValueError, KeyError, TypeError):pass
        return reply('Operazione non completata: '+str(exc)+'. Riapri il menu.')


def _authorized(message, sender, cfg):
    return (str(message.get('chat',{}).get('id'))==str(cfg['telegram_chat_id']) and
            str(sender.get('id'))==str(cfg.get('telegram_user_id') or cfg['telegram_chat_id']) and not sender.get('is_bot'))
