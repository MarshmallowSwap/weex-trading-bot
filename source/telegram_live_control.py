"""Pure authenticated Telegram command handler; returns replies, never sends them."""
import json,time
from pathlib import Path
from datetime import datetime
import live_control as control

COMMANDS=[{'command':'blocchi','description':'Mostra dettaglio e azioni per i blocchi LIVE'},
          {'command':'risolvi','description':'Ricostruisce una chiusura: simbolo e ID ordine facoltativo'},{'command':'riconcilia','description':'Verifica chiusure e rimuove TP residui; ferma ingressi'},{'command':'live_start','description':'Prepara avvio trading reale con conferma'},
          {'command':'live_stop','description':'Ferma nuovi ingressi; conserva i TP'},
          {'command':'live_status','description':'Stato reale del runner e blocchi'},
          {'command':'live_test_once','description':'Preflight di un test live, senza inviare ordini'},
          {'command':'crossclose','description':'Conferma monouso chiusura ETH CROSS 1x protetta'},
          {'command':'tradingmode','description':'Automatico, solo alert, misto o solo manuale'}]

def _manual_shape(text):
    parts=str(text or '').strip().split()
    if len(parts)!=2:return False
    try:
        from weex_trading_modes import normalize_symbol
        normalize_symbol(parts[0]);return True
    except ValueError:return False

def fresh_start_message(message,now=None):
    # Telegram stamps messages on its server. Allow small clock skew, but never
    # extend the age limit for queued commands or the nonce confirmation TTL.
    stamp=message.get('date')
    if isinstance(stamp,bool) or not isinstance(stamp,int) or stamp<=0:return False
    age=(time.time() if now is None else now)-stamp
    return -30<=age<=120

def handle(update,cfg,root=control.ROOT):
    cb=update.get('callback_query');m=(cb or {}).get('message') if cb else update.get('message')
    m=m or {};sender=(cb or m).get('from') or {}
    text=str(m.get('text','')).strip()
    data=str(cb.get('data','')) if cb else text.split(' ')[0].split('@')[0].lower()
    manual_shape=not cb and _manual_shape(text)
    if not (data in ('/live_start','/live_stop','/live_status','/live_test_once','/tradingmode','/riconcilia','/risolvi','/blocchi','/crossclose') or
            data.startswith(('livectl:','liveack:manual:','tradingmode:','crossclose:confirm:')) or manual_shape):return None
    chat=str(m.get('chat',{}).get('id'));user=str(sender.get('id'))
    if chat!=str(cfg['telegram_chat_id']) or user!=str(cfg.get('telegram_user_id') or cfg['telegram_chat_id']) or sender.get('is_bot'):
        return {'handled':True,'reply':None}
    def reply(text,keyboard=None):
        r={'chat_id':chat,'text':text}
        if keyboard:r['reply_markup']=keyboard
        from telegram_button_menu import decorate
        return decorate({'handled':True,'reply':r},root)
    if data=='/crossclose':
        if cb or not fresh_start_message(m):return reply('Conferma non valida o scaduta. Riprova /crossclose.')
        try:
            from weex_cross_1x_operator_telegram_20261109 import challenge
            request=challenge(root,user,chat)
            scope=request['scope']
            msg=('Richiesta chiusura supervisionata ETHUSDT CROSS 1x\\n'
                 +'Pilot: '+scope['pilotId']+'\\nOrdine: '+scope['entryOrderId']
                 +'\\nPosizione: '+scope['positionId']+'\\nStop: '+scope['stopAlgoId']
                 +'\\nConferma monouso entro 120 secondi.\\n'
                 +'Questa conferma NON invia ordini e NON avvia il trading.')
            return reply(msg,{'inline_keyboard':[[{'text':'Confermo solo questa chiusura',
              'callback_data':'crossclose:confirm:'+request['nonce']}]]})
        except Exception as exc:
            reason=str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__
            return reply('Chiusura non autorizzabile: '+reason+'. Nessun ordine inviato.')
    if data.startswith('crossclose:confirm:'):
        if not cb:return reply('Solo il pulsante Telegram puo confermare.')
        try:
            from weex_cross_1x_operator_telegram_20261109 import confirm
            accepted=confirm(root,data.split(':',2)[2],user,chat)
        except Exception:accepted=False
        return reply('Conferma monouso registrata. Nessun ordine inviato. Esecutore ancora disarmato.'
                     if accepted else 'Conferma scaduta, cambiata o non valida. Nessun ordine inviato.')
    if data in ('/blocchi','livectl:blocks'):
        from weex_reconcile import diagnostics
        from telegram_button_menu import blocks_keyboard
        try:return reply(diagnostics(root,text.split()[1] if not cb and len(text.split())>1 else None),blocks_keyboard(root))
        except ValueError:return reply('Usa /blocchi oppure /blocchi AAVE.')
    if data=='/risolvi' or data.startswith('livectl:resolve:'):
        if not cb and not fresh_start_message(m):return reply('Comando scaduto. Invia nuovamente /risolvi SIMBOLO.')
        try:
            from weex_trading_modes import normalize_symbol
            parts=text.split() if not cb else ['/risolvi',data.split(':',2)[2]]
            if not 2<=len(parts)<=7:raise ValueError('ARGS')
            symbol=normalize_symbol(parts[1]);ids=parts[2:]
            if any(not oid.isascii() or not oid.isdigit() or not 1<=len(oid)<=20 for oid in ids):raise ValueError('IDS')
        except ValueError:return reply('Usa /risolvi AAVE. Per indicare una chiusura manuale: /risolvi AAVE ID_ORDINE (fino a 5 ID separati da spazi).')
        result=reply('Avvio ricostruzione '+symbol+': fermerò i nuovi ingressi e controllerò storico, TP, ordini indicati ed eseguiti. Ti invierò l’esito e le azioni disponibili.')
        result['reconcileRequest']={'user':user,'chat':chat,'symbol':symbol,'orderIds':ids}
        return result
    if data in ('/riconcilia','livectl:reconcile'):
        if not cb and not fresh_start_message(m):return reply('Comando scaduto. Invia nuovamente /riconcilia.')
        result=reply('Richiesta di riconciliazione ricevuta. Fermerò i nuovi ingressi, verificherò le chiusure e rimuoverò solo i TP residui delle posizioni già chiuse. Le posizioni aperte restano invariate. Ti invierò il risultato; l’attesa API può richiedere alcuni minuti.')
        result['reconcileRequest']={'user':user,'chat':chat}
        return result
    if data in ('/live_test_once','livectl:test_once'):
        try:
            from live_test_once_preflight import telegram_text
            return reply(telegram_text(root))
        except Exception as exc:
            reason=str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__
            return reply('🧪 LIVE TEST — SOLO VERIFICA\nPreflight non completato: '+reason+'\nOrdine inviato: NO.')
    if data=='/tradingmode' or data=='tradingmode:show':
        from telegram_ai_fullmenu import trading_mode_menu,trading_mode_text
        return reply(trading_mode_text(),trading_mode_menu())
    if data.startswith('tradingmode:set:'):
        from weex_trading_modes import MODES,set_mode
        mode=data.split(':',2)[2]
        if mode not in MODES:return reply('Modalità non riconosciuta.')
        # A mode transition never starts entries. It invalidates live challenges and
        # requires the normal /live_start confirmation before active modes can trade.
        control.stop(user,chat,root)
        set_mode(root,mode,user)
        from telegram_ai_fullmenu import trading_mode_menu
        if mode=='alerts_only':
            message='✅ Solo alert attivo. La scansione e gli avvisi continuano; nuovi ingressi fermi.'
        elif mode=='automatic':
            message='✅ Modalità automatica selezionata. Nuovi ingressi restano fermi: usa /live_start e conferma.'
        elif mode=='manual_only':
            message=('✅ Solo manuale selezionato. Il bot aprirà soltanto dai comandi TOKEN LONG o TOKEN SHORT, '
                     'con costo, leva e TP configurati. Usa /live_start e conferma per abilitare gli ingressi manuali.')
        else:
            message=('✅ Automatico + manuale selezionato. In Telegram potrai inviare `SOL LONG` o `SOL SHORT`; '
                     'le richieste manuali usano costo, leva e TP configurati e non consumano il limite automatico. '
                     'Nuovi ingressi restano fermi: usa /live_start e conferma.')
        return reply(message,trading_mode_menu())
    if manual_shape:
        from weex_trading_modes import get_mode,enqueue_manual,parse_manual_command
        mode=get_mode(root)['mode']
        try:parsed=parse_manual_command(text)
        except ValueError:
            return reply('Formato non valido. Usa `TOKEN LONG` oppure `TOKEN SHORT`, ad esempio `SOL LONG`.')
        if mode not in ('automatic_manual','manual_only'):
            return reply('Comando manuale non eseguito: seleziona Solo manuale oppure Automatico + manuale nel menu Trading.')
        if control.state(root)['mode']!='RUNNING':
            return reply('Comando manuale non eseguito: nuovi ingressi fermi. Avvia con /live_start e conferma.')
        errors=control.readiness(root)
        if errors:
            return reply('Comando manuale non eseguito: runner bloccato ('+', '.join(errors)+'). Nessun ordine inviato.')
        symbol,side=parsed
        try:req=enqueue_manual(root,symbol,side,user)
        except Exception as exc:
            code=str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__
            return reply('Comando manuale non accodato: '+code+'. Nessun nuovo ordine inviato.')
        result=reply(f"Ricevuto {symbol} {side}. Avvio immediato dei controlli; l’ordine parte solo se conto, libro, costo, leva e TP sono verificati.")
        result['manualRequest']=req
        return result
    if data.startswith('liveack:manual:'):
        token=data.split(':',2)[2]
        try:
            from weex_manual_position_ack import request_ack
            accepted=request_ack(root,token,user,chat)
        except Exception:
            accepted=False
        if accepted:
            return reply('✅ Conferma ricevuta. Al prossimo controllo il runner verificherà che sia ancora la stessa posizione WLD. Se corrisponde, questo specifico blocco sarà ignorato; gli altri blocchi restano attivi.')
        return reply('Questa conferma è scaduta o non è più valida. Controlla /live_status per il blocco aggiornato.')
    if data in ('/live_stop','livectl:stop'):
        control.stop(user,chat,root)
        return reply('⏹ Nuovi ingressi LIVE fermati. Un ordine già in invio può essere completato prima dello stop. I TP esistenti e il recupero delle posizioni del bot restano attivi; nessuna chiusura forzata.')
    if data in ('/live_status','livectl:status'):
        errors=control.readiness(root);s=control.state(root)
        from weex_trading_modes import get_mode
        mode=get_mode(root)['mode']
        try:
            h=json.loads((Path(root)/'weex_live_worker_latest.json').read_text(encoding='utf-8'))
            extra=f"\nUltimo ciclo: {h.get('checkedAt')}\nEsito: {h.get('status')}\nPosizioni/ordini conteggiati: {h.get('capacity',{}).get('count','n/d')}"
            if h.get('reason'):extra+='\nMotivo: '+str(h['reason'])
        except Exception:extra='\nNessun ciclo osservato.'
        try:
            rec=json.loads((Path(root)/'weex_reconcile_latest.json').read_text(encoding='utf-8'))
            if rec.get('status') in ('RUNNING','WAIT_API','VERIFYING'):
                extra+='\nRiconciliazione: '+{'RUNNING':'verifica in corso','WAIT_API':'attesa quota API','VERIFYING':'controllo finale'}[rec['status']]
        except (OSError,ValueError,TypeError):pass
        return reply(control.display(root)+extra+f"\nModalità: {mode}"+'\n'+('Blocchi: '+', '.join(errors) if errors else 'Controlli di avvio disponibili; ogni ingresso resta soggetto ai controlli configurati.'))
    if data in ('/live_start','livectl:start'):
        if not cb and not fresh_start_message(m):return reply('Comando di avvio scaduto o orario non valido. Invia nuovamente /live_start.')
        p=control.request_start(user,chat,root)
        if not p['accepted']:return reply('Avvio non eseguito: '+', '.join(p['errors']))
        limit_text=('Ingressi solo su comando: TOKEN LONG oppure TOKEN SHORT.' if p.get('tradingMode')=='manual_only'
                    else f"Massimo: {p['maxPositions']} posizioni automatiche")
        return reply(f"Avvio {p['tradingModeLabel']} su FONDI REALI\nCosto per ingresso: {p['cost']} USDT (margine + commissione)\n{limit_text}\n{p.get('tpDescription', 'TP: '+p['tp']+' USDT oltre break-even stimato')}\nLeva massima disponibile, minimo {p['minimumLeverage']}×; Cross; SL OFF.\n\nConferma entro 2 minuti. /live_stop blocca i nuovi ingressi.",
            {'inline_keyboard':[[{'text':'CONFERMO AVVIO LIVE','callback_data':'livectl:confirm:'+p['nonce']}],
                                [{'text':'Annulla / resta fermo','callback_data':'livectl:stop'}]]})
    if data.startswith('livectl:confirm:'):
        r=control.confirm_start(data.split(':',2)[2],user,chat,root)
        from weex_trading_modes import get_mode
        started_text=('▶ Solo manuale LIVE attivo. Invia TOKEN LONG o TOKEN SHORT; il bot applicherà costo, leva e TP configurati. /live_stop ferma i nuovi ingressi.'
                      if get_mode(root)['mode']=='manual_only' else '▶ Avvio LIVE autorizzato da te. Il runner considererà i segnali nei prossimi cicli; /live_status mostra l’esito. /live_stop ferma nuovi ingressi.')
        return reply(started_text if r['started'] else 'Avvio non eseguito: '+', '.join(r['errors']))
    return reply('Comando non riconosciuto. Usa /live_status.')
