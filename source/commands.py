import json,logging,sqlite3,time,urllib.request,threading
from pathlib import Path
from decimal import Decimal
from telegram_cost_settings import begin as begin_cost, accept as accept_cost
from telegram_ai_settings import message as ai_message, keyboard as ai_keyboard, save_profit as ai_save_profit, validate as ai_validate
from agents_status import status as agent_status
from telegram_ai_fullmenu import summary as full_summary,home_text,menu as full_menu,trading_menu,monitoring_menu,positions_menu,set_positions,sl_menu,set_sl,tp_modes_menu,select_strategy
from agents_status_card import render as render_agents_card
from settings_card import render as render_settings_card
from monitor import ROOT,TG,query,direction
import sys
sys.path.insert(0,r"D:\FUNDSHOT\hyperliquid_alerts")
from photo import send_photo
from weex_alert_archive import photo_sender,observed,file_photo_sender
send_photo=photo_sender(send_photo,ROOT,"commands.statistics")

DB=ROOT/"telegram_commands.sqlite3"
_menu_report_lock=threading.Lock()
logging.basicConfig(filename=str(ROOT/"commands.log"),level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
def _api_send(token,method,args):
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/"+method,
        json.dumps(args).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=25) as r: value=json.load(r)
    if not value.get("ok"):raise RuntimeError("Telegram failure: "+method)
    return value.get("result")
def api(token,method,args):
    if method!='sendMessage':return _api_send(token,method,args)
    args.setdefault('reply_markup',full_menu())
    # No incoming updates, identity config, callback nonce or keyboard.
    return observed(ROOT,'commands.reply',method,{'text':args.get('text')},lambda:_api_send(token,method,args))

def _run_reconciliation(token,chat,user,symbol=None,order_ids=()):
    from weex_reconcile import run,message,keyboard
    result=None
    try:
        kwargs={'symbol':symbol,'order_ids':order_ids} if symbol else {}
        result=run(ROOT,user,chat,**kwargs);text=message(result)
    except Exception:
        logging.exception('User reconciliation failed')
        text='Riconciliazione non completata. Controlla /live_status e riprova /riconcilia.'
    try:
        response={'chat_id':chat,'text':text}
        if result:response['reply_markup']=keyboard(result)
        api(token,'sendMessage',response)
    except Exception:logging.exception('Reconciliation result notification failed')

def _run_manual_request(token,chat,request_id,symbol,side):
    """Run one queued user-directed entry off the Telegram polling thread."""
    from weex_live_worker import run
    deadline=time.monotonic()+28
    result=None
    while time.monotonic()<deadline:
        try:
            result=run(ROOT,manual_only=True,manual_request_id=request_id)
        except RuntimeError as exc:
            if str(exc)!='CYCLE_ALREADY_RUNNING':
                logging.exception('Manual live cycle failed before a report')
                result={'status':'BLOCKED','reason':type(exc).__name__};break
            time.sleep(.75);continue
        except Exception as exc:
            logging.exception('Manual live cycle failed before a report')
            result={'status':'BLOCKED','reason':type(exc).__name__};break
        if result.get('reason')!='CYCLE_ALREADY_RUNNING':break
        time.sleep(.75)
    requests=result.get('manualRequests',[]) if isinstance(result,dict) else []
    item=next((x for x in requests if x.get('id')==request_id),None)
    queue_state=None
    if not item:
        try:
            from weex_trading_modes import connect
            q=connect(ROOT)
            try:
                row=q.execute('SELECT state FROM manual_requests_v1 WHERE id=?',(request_id,)).fetchone()
                queue_state=row['state'] if row else None
            finally:q.close()
        except Exception:logging.exception('Could not inspect manual request status')
    if item and item.get('state') in ('PROTECTED','CLOSED'):
        message=(f"✅ {symbol} {side}: posizione aperta e protetta dal TP. "
                 "La posizione è gestita dal bot e non occupa uno slot automatico.")
    elif (item and item.get('state')=='REVIEW_REQUIRED') or queue_state=='PROCESSING':
        message=(f"⚠️ {symbol} {side}: esito dell’invio da riconciliare. Non reinviare il comando; "
                 "il runner controllerà la posizione e il TP.")
    else:
        reason=(item or {}).get('reason') or (result or {}).get('status','ESITO_NON DISPONIBILE')
        message=f"⛔ {symbol} {side}: nessuna apertura confermata ({reason}). Non è stato ripetuto l’ordine."
    if not item and queue_state=='PENDING':
        try:
            from weex_trading_modes import cancel_pending_request
            cancel_pending_request(ROOT,request_id,'MANUAL_WORKER_DID_NOT_CLAIM')
        except Exception:logging.exception('Could not expire unclaimed manual request')
    try:api(token,'sendMessage',{'chat_id':chat,'text':message})
    except Exception:logging.exception('Telegram manual entry result notification failed')


def _run_menu_report(token,chat,action):
    """Read-only reports and proposal preparation must not delay the STOP button."""
    from telegram_button_menu import monitoring,recovery
    try:
        if action=='card':
            send_settings_card(token,chat)
            return
        if action in ('tp_check','tp_repair'):
            if action=='tp_check':
                from weex_bot_tp_audit import inspect
                states=inspect(ROOT)
                lines=[f"{x['symbol']}: {x['status']} ({x.get('state','UNKNOWN')})" for x in states]
                caption='Verifica TP su WEEX e registro bot\n'+('\n'.join(lines) or 'Nessuna posizione del bot da controllare.')+'\nNessun ordine inviato.'
            else:
                from weex_tp_repair_preflight import preflight
                states=preflight(ROOT,save_proposals=True)
                lines=[f"{x['symbol']}: {x['auditStatus']} / {x['decision']}"+(' / '+x['journal']['state'] if x.get('journal') else '') for x in states]
                caption='Proposte recupero TP\n'+('\n'.join(lines) or 'Nessuna posizione del bot da controllare.')+'\nSolo verifica e proposte: invio ordini DISABILITATO.'
            markup=recovery()
        else:
            kind,fields,caption=build('/'+action,snapshot())
            markup=monitoring()
        api(token,'sendMessage',{'chat_id':chat,'text':caption[:4000],'reply_markup':markup})
    except Exception:
        logging.exception('Button report failed')
        try:api(token,'sendMessage',{'chat_id':chat,'text':'Lettura non completata. Riprova dal menu.','reply_markup':full_menu()})
        except Exception:logging.exception('Report failure notification failed')
    finally:_menu_report_lock.release()

def send_agents_photo(token,chat,keyboard=None):
    image_path,states=render_agents_card()
    boundary="----WEEXAIStatusBoundary"
    caption="🤖 WEEX AI DESK — Stato reale\nScanner: "+states["scanner"]+" | Strategy: "+states["strategy"]+"\nLive: "+("AVVIO ABILITATO" if states["live"] else "INGRESSI FERMI")
    data=image_path.read_bytes()
    body=b""
    if keyboard:
        body+=("--"+boundary+"\r\nContent-Disposition: form-data; name=\"reply_markup\"\r\n\r\n"+json.dumps(keyboard,ensure_ascii=False)+"\r\n").encode("utf-8")
    body+=(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n"+chat+"\r\n"
           "--"+boundary+"\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"agents_status.png\"\r\n"
           "Content-Type: image/png\r\n\r\n").encode("utf-8")+data+("\r\n--"+boundary+"--\r\n").encode("utf-8"))
    request=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendPhoto",body,headers={"Content-Type":"multipart/form-data; boundary="+boundary})
    with urllib.request.urlopen(request,timeout=30) as response:
        result=json.load(response)
    if not result.get("ok"):raise RuntimeError("Telegram sendPhoto error")
    return result["result"]

def edit_menu_view(token,callback,text,keyboard):
    message=callback.get("message") or {}
    args={"chat_id":str(message.get("chat",{}).get("id")),"message_id":message.get("message_id"),
          "reply_markup":keyboard}
    if message.get("photo"):
        method="editMessageCaption";args["caption"]=text
    else:
        method="editMessageText";args["text"]=text
    return api(token,method,args)

def send_settings_card(token,chat):
    image_path=render_settings_card()
    boundary="----WEEXSettingsCardBoundary"
    keyboard_data=json.dumps(full_menu(),ensure_ascii=False)
    data=image_path.read_bytes()
    fields=[("chat_id",chat),("caption",home_text()),("reply_markup",keyboard_data)]
    body=b""
    for key,value in fields:
        body+=("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+key+"\"\r\n\r\n"+value+"\r\n").encode("utf-8")
    body+=("--"+boundary+"\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"settings.png\"\r\nContent-Type: image/png\r\n\r\n").encode("utf-8")+data+("\r\n--"+boundary+"--\r\n").encode("utf-8")
    request=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendPhoto",body,headers={"Content-Type":"multipart/form-data; boundary="+boundary})
    with urllib.request.urlopen(request,timeout=30) as resp:result=json.load(resp)
    if not result.get("ok"):raise RuntimeError("settings sendPhoto failed")
    return result["result"]

send_agents_photo=file_photo_sender(send_agents_photo,ROOT,'commands.agents','agents_status_live.png','agents_status')
send_settings_card=file_photo_sender(send_settings_card,ROOT,'commands.settings','settings_live.png','settings')

def live_control_text():
    from live_control import display
    return display(ROOT)+" · /live_status per blocchi e dettagli."

def snapshot():
    # The WEEX endpoint limit is 100. These metrics are a recent-fill sample, NOT guaranteed 30-day complete.
    rows=query("/capi/v3/userTrades?limit=100")
    if not isinstance(rows,list):raise ValueError("Unexpected WEEX trades response")
    rows=[r for r in rows if int(r.get("time") or 0)>=int(time.time()*1000)-30*86400000]
    closes=[r for r in rows if direction(r)[0]=="close"]
    pnl=sum((Decimal(str(r.get("realizedPnl") or 0)) for r in rows),Decimal(0))
    fees=sum((Decimal(str(r.get("commission") or 0)) for r in rows),Decimal(0))
    wins=sum(Decimal(str(r.get("realizedPnl") or 0))>0 for r in closes)
    losses=sum(Decimal(str(r.get("realizedPnl") or 0))<0 for r in closes)
    return rows,pnl,fees,int(wins),int(losses),len(closes)-int(wins)-int(losses)
def build(cmd,data):
    rows,pnl,fee,wins,losses,flats=data
    caveat="Campione: massimo 100 esecuzioni recenti WEEX entro 30 giorni; non storico completo."
    if cmd=="/pnl":
        fields=[("PNL LORDO",f"{pnl:+.4f} USDT"),
                ("FEE",f"{fee:.4f} USDT"),
                ("PNL NETTO",f"{pnl-fee:+.4f} USDT"),
                ("FILL",len(rows)),("PERIODO","MAX 30 GG")]
        caption=(f"WEEX | PNL realizzato lordo: {pnl:+.4f} USDT\n"
                 f"Commissioni: {fee:.4f} (valute di commissione non normalizzate)\n"
                 f"Netto indicativo: {pnl-fee:+.4f}\n{caveat}\n"
                 "Funding e PnL non realizzato esclusi.")
        return "pnl",fields,caption
    total=wins+losses
    rate=f"{wins/total*100:.2f}%" if total else "N/D"
    fields=[("RATE",rate),("WINS",wins),("LOSSES",losses),
            ("BREAKEVEN",flats),("PERIODO","MAX 30 GG")]
    caption=(f"WEEX | WIN RATE FILL DI CHIUSURA: {rate}\n"
             f"Vincenti: {wins}; perdenti: {losses}; pari: {flats}\n{caveat}\n"
             "Non equivale al win rate di posizioni complete.")
    return "winrate",fields,caption

def main():
    conn=sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS cursor(name TEXT PRIMARY KEY,value INTEGER NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS input_state(chat_id TEXT PRIMARY KEY, mode TEXT NOT NULL)")
    conn.commit()
    while True:
        try:
            cfg=json.loads(TG.read_text(encoding="utf-8"))
            token=cfg["telegram_bot_token"]
            chat=str(cfg["telegram_chat_id"])
            state=conn.execute("SELECT value FROM cursor WHERE name='offset'").fetchone()
            args={"timeout":0,"limit":100,"allowed_updates":["message","callback_query"]}
            if state:args["offset"]=state[0]
            updates=api(token,"getUpdates",args)
            from weex_service_health import publish
            publish(ROOT,"telegram")
            for update in updates:
                ident=int(update["update_id"])
                # Live control runs before pending Cost/TP text input; STOP always wins.
                from telegram_live_control import handle as handle_live_control
                from telegram_button_menu import handle as handle_buttons, decorate, monitoring
                live_result=handle_buttons(update,cfg,ROOT)
                if live_result is None:live_result=handle_live_control(update,cfg,ROOT)
                live_result=decorate(live_result,ROOT)
                if live_result is not None:
                    if live_result.get('clearInput') or live_result.get('buttonUI'):
                        conn.execute('DELETE FROM input_state WHERE chat_id=?',(chat,))
                    if live_result.get("reply"):
                        if live_result.get('buttonUI') and update.get('callback_query'):
                            try:edit_menu_view(token,update['callback_query'],live_result['reply']['text'],live_result['reply']['reply_markup'])
                            except Exception:api(token,"sendMessage",live_result['reply'])
                        else:api(token,"sendMessage",live_result["reply"])
                    action=live_result.get('menuAction')
                    if action:
                        if _menu_report_lock.acquire(blocking=False):
                            try:threading.Thread(target=_run_menu_report,args=(token,chat,action),name='weex-menu-report',daemon=True).start()
                            except BaseException:
                                _menu_report_lock.release();raise
                        else:api(token,'sendMessage',{'chat_id':chat,'text':'Un riepilogo è già in preparazione. Attendi il risultato.'})
                    if update.get("callback_query"):
                        api(token,"answerCallbackQuery",{"callback_query_id":update["callback_query"]["id"]})
                    conn.execute("INSERT INTO cursor VALUES ('offset',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(ident+1,))
                    conn.commit()
                    reconcile=live_result.get('reconcileRequest')
                    if reconcile:
                        threading.Thread(target=_run_reconciliation,
                            args=((token,reconcile['chat'],reconcile['user'],reconcile['symbol'],reconcile.get('orderIds',[]))
                                  if reconcile.get('symbol') else (token,reconcile['chat'],reconcile['user'])),
                            name='weex-reconcile',daemon=True).start()
                    manual=live_result.get('manualRequest')
                    if manual:
                        threading.Thread(target=_run_manual_request,
                            args=(token,chat,manual['id'],manual['symbol'],manual['side']),
                            name='weex-manual-entry',daemon=True).start()
                    continue
                from telegram_position_reports import handle as handle_position_reports
                report_result=handle_position_reports(update,cfg,ROOT)
                if report_result:
                    if isinstance(report_result,dict) and report_result.get('notice'):
                        api(token,"sendMessage",{"chat_id":chat,"text":report_result['notice']})
                    if update.get("callback_query"):
                        try:api(token,"answerCallbackQuery",{"callback_query_id":update["callback_query"]["id"],"text":"Preparazione riepilogo grafico"})
                        except Exception:logging.warning("Report callback acknowledgement failed")
                    conn.execute("INSERT INTO cursor VALUES ('offset',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(ident+1,))
                    conn.commit()
                    continue
                callback=update.get("callback_query")
                if callback:
                    m=callback.get("message") or {}
                    callback_chat=str(m.get("chat",{}).get("id"))
                    callback_from=str(callback.get("from",{}).get("id"))
                    allowed_user=str(cfg.get("telegram_user_id") or chat)
                    if callback_chat==chat and callback_from==allowed_user and not callback.get('from',{}).get('is_bot'):
                        choice=str(callback.get("data") or "")
                        try:
                            if choice=="aimenu:home":
                                edit_menu_view(token,callback,home_text(),full_menu())
                            elif choice=="aimenu:trade":
                                cfg_text="📈 TRADING\n\n"+full_summary()+"\n\nPrepara l’avvio LIVE e conferma. Per un ingresso manuale premi Apri posizione manuale."
                                edit_menu_view(token,callback,cfg_text,trading_menu())
                            elif choice=="aimenu:monitor":
                                edit_menu_view(token,callback,"📊 POSIZIONI E RISULTATI\n\nConsulta posizioni, chiusure, statistiche e coppie candidate.\n"+live_control_text(),monitoring_menu())
                            elif choice=="aimenu:candidates":
                                from monitor import candidate_report
                                api(token,"sendMessage",{"chat_id":chat,"text":candidate_report()['text'],
                                    "reply_markup":{"inline_keyboard":[[{"text":"🔄 Aggiorna candidate","callback_data":"aimenu:candidates"}],
                                                                       [{"text":"⬅️ Monitoraggio","callback_data":"aimenu:monitor"}]]}})
                            elif choice=="aimenu:agents":
                                send_agents_photo(token,chat,{"inline_keyboard":[[{"text":"⬅️ Monitoraggio","callback_data":"aimenu:monitor"}]]})
                            elif choice=="aimenu:tp":
                                api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":tp_modes_menu()})
                            elif choice=="aitpmode:amount":
                                api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":ai_keyboard()})
                            elif choice in ("aitpmode:fixed","aitpmode:trailing"):
                                from live_control import stop
                                stop(callback_from,chat,ROOT)
                                mode=select_strategy("tp",choice.split(":")[1])
                                api(token,"sendMessage",{"chat_id":chat,"text":ai_message()+"\n\nLa nuova modalità vale per i prossimi ingressi. Le uscite già impostate restano gestite con i parametri originali. Premi Prepara avvio LIVE e conferma per ripartire.","reply_markup":tp_modes_menu()})
                            elif choice.startswith("aitpmode:"):
                                from live_control import stop
                                stop(callback_from,chat,ROOT)
                                mode=select_strategy("tp",choice.split(":")[1])
                                api(token,"sendMessage",{"chat_id":chat,"text":f"✅ TP modello {mode.upper()} selezionato. Questa modalità di calcolo non abilita nuovi ingressi live; controlla /live_status.","reply_markup":tp_modes_menu()})
                            elif choice=="aimenu:cost":
                                api(token,"sendMessage",{"chat_id":chat,"text":begin_cost(conn,chat)})
                            elif choice=="aimenu:positions":
                                api(token,"sendMessage",{"chat_id":chat,"text":"📊 Scegli il massimo di posizioni (1–10):","reply_markup":positions_menu()})
                            elif choice=="aimenu:sl":
                                api(token,"sendMessage",{"chat_id":chat,"text":"🛑 SL attualmente OFF. L'opzione futura richiederà prezzo/modalità e verifica del rischio.","reply_markup":sl_menu()})
                            elif choice.startswith("aipos:"):
                                from live_control import stop
                                stop(callback_from,chat,ROOT)
                                n=set_positions(choice.split(":")[1])
                                api(token,"sendMessage",{"chat_id":chat,"text":f"✅ Limite configurato: {n} posizioni automatiche. Nessun ordine eseguito. Ingressi fermati: prepara e conferma l’avvio.","reply_markup":trading_menu()})
                            elif choice=="aisl:off":
                                from live_control import stop
                                stop(callback_from,chat,ROOT)
                                set_sl(False)
                                api(token,"sendMessage",{"chat_id":chat,"text":"✅ SL confermato OFF. Stato trading: /live_status.","reply_markup":full_menu()})
                            elif choice.startswith("aisl:"):
                                from live_control import stop
                                stop(callback_from,chat,ROOT)
                                mode=select_strategy("sl",choice.split(":")[1])
                                api(token,"sendMessage",{"chat_id":chat,"text":f"✅ SL modello {mode.upper()} selezionato SOLO per calcoli. Nessuno stop reale attivo.","reply_markup":sl_menu()})
                            elif choice=="aitp:custom":
                                conn.execute("INSERT INTO input_state VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET mode=excluded.mode",(chat,"await_custom_tp"))
                                conn.commit()
                                api(token,"sendMessage",{"chat_id":chat,"text":"✏️ Invia il profitto lordo desiderato in USDT (es. 1,75). /cancel per annullare."})
                            elif choice=="aitp:show":
                                api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":ai_keyboard()})
                            elif choice.startswith("aitp:"):
                                val=choice.partition(":")[2]
                                if val in ("0.50","1.00","2.00","5.00","20.00"):
                                    amount=ai_save_profit(val)
                                    api(token,"sendMessage",{"chat_id":chat,"text":f"✅ TP configurato: +{amount:.2f} USDT lordi, prima di fee e slippage. Ingressi LIVE fermati; nessun ordine inviato."})
                        except Exception:
                            logging.exception("WEEX menu callback failed")
                            api(token,"sendMessage",{"chat_id":chat,"text":"Operazione non completata. Controlla lo stato e riprova dal menu.","reply_markup":full_menu()})
                    try:
                        api(token,"answerCallbackQuery",{"callback_query_id":callback["id"]})
                    except Exception: logging.exception("Telegram callback acknowledge failed")
                    conn.execute("INSERT INTO cursor VALUES ('offset',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(ident+1,))
                    conn.commit()
                    continue
                m=update.get("message",{})
                command=str(m.get("text","")).strip().split(" ")[0].split("@")[0].lower()
                if str(m.get("chat",{}).get("id"))==chat:
                    from_id=str(m.get("from",{}).get("id"))
                    allowed_user=str(cfg.get("telegram_user_id") or chat)
                    if command in ('collaudo','/collaudo') and from_id==allowed_user and not m.get('from',{}).get('is_bot'):
                        from telegram_live_control import fresh_start_message
                        if not fresh_start_message(m):
                            api(token,'sendMessage',{'chat_id':chat,'text':'COLLAUDO scaduto: reinvia il comando. Nessun ordine inviato.'})
                        else:
                            from weex_telegram_collaudo import start_telegram
                            started=start_telegram(api,token,chat,ROOT)
                            api(token,'sendMessage',{'chat_id':chat,'text':
                                'COLLAUDO avviato: controllo conto e crash locale, senza ordini reali.' if started
                                else 'COLLAUDO gia in esecuzione: attendi il resoconto.'})
                    elif command=="/settings" and from_id==allowed_user:
                        send_settings_card(token,chat)
                    elif from_id==allowed_user and command=="/cancel":
                        conn.execute("DELETE FROM input_state WHERE chat_id=?",(chat,))
                        api(token,"sendMessage",{"chat_id":chat,"text":"Inserimento impostazione annullato."})
                    elif from_id==allowed_user and command=="/cost":
                        api(token,"sendMessage",{"chat_id":chat,"text":begin_cost(conn,chat)})
                    elif command in ("/tp_check","/tp_repair") and from_id==allowed_user:
                        try:
                            if command=="/tp_check":
                                from weex_bot_tp_audit import inspect
                                states=inspect(ROOT)
                                lines=[f"{x['symbol']}: {x['status']} ({x.get('state','UNKNOWN')})" for x in states]
                                message="TP AUDIT — verifica WEEX e registro bot\n"+("\n".join(lines) if lines else "Nessuna posizione del bot da controllare.")+"\nNessun ordine inviato."
                            else:
                                from weex_tp_repair_preflight import preflight
                                states=preflight(ROOT,save_proposals=True)
                                lines=[f"{x['symbol']}: {x['auditStatus']} / {x['decision']}"+(" / "+x['journal']['state'] if x.get('journal') else "") for x in states]
                                message="TP REPAIR — riconciliazione storica e registro proposte\n"+("\n".join(lines) if lines else "Nessuna posizione del bot da controllare.")+"\nSolo proposte, invio ordini DISABILITATO."
                            api(token,"sendMessage",{"chat_id":chat,"text":message})
                        except Exception:
                            logging.exception("WEEX TP audit command failed")
                            api(token,"sendMessage",{"chat_id":chat,"text":"Controllo TP non disponibile. Nessun ordine inviato."})
                    elif command=="/candidates" and from_id==allowed_user:
                        from monitor import candidate_report
                        api(token,"sendMessage",{"chat_id":chat,"text":candidate_report()['text']})
                    elif from_id==allowed_user and conn.execute("SELECT mode FROM input_state WHERE chat_id=?",(chat,)).fetchone()==("await_custom_cost",):
                        try:
                            result=accept_cost(conn,chat,str(m.get("text","")))
                            api(token,"sendMessage",{"chat_id":chat,"text":result})
                        except ValueError as e:
                            api(token,"sendMessage",{"chat_id":chat,"text":str(e)+"\nRiprova oppure /cancel."})
                    elif from_id==allowed_user and conn.execute("SELECT mode FROM input_state WHERE chat_id=?",(chat,)).fetchone()==("await_custom_tp",):
                        try:
                            amount=ai_save_profit(str(m.get("text","")))
                            conn.execute("DELETE FROM input_state WHERE chat_id=?",(chat,))
                            api(token,"sendMessage",{"chat_id":chat,"text":f"✅ TP personalizzato: +{amount:.2f} USDT lordi, prima di fee e slippage. Ingressi LIVE fermati; nessun ordine inviato."})
                        except ValueError as e:
                            api(token,"sendMessage",{"chat_id":chat,"text":str(e)+"\nRiprova oppure /cancel."})
                    elif command=="/agents" and from_id==allowed_user:
                        try:
                            send_agents_photo(token,chat)
                        except Exception:
                            logging.exception("WEEX AI graphic failed")
                            api(token,"sendMessage",{"chat_id":chat,"text":agent_status()})
                    elif command in ("/pnl","/winrate") and from_id==allowed_user and not m.get('from',{}).get('is_bot'):
                        try:
                            kind,fields,caption=build(command,snapshot())
                            send_photo(cfg,kind,fields,caption)
                        except Exception:
                            logging.exception("WEEX command error")
                            api(token,"sendMessage",{"chat_id":chat,"text":"WEEX: errore lettura statistiche. Riprova."})
                    elif command in ("/start","/help") and from_id==allowed_user:
                        api(token,"sendMessage",{"chat_id":chat,"text":home_text()+"\n\n/riconcilia, /live_start, /live_stop, /live_status e /live_test_once (solo verifica, nessun ordine) restano disponibili anche come comandi.","reply_markup":full_menu()})
                conn.execute("INSERT INTO cursor VALUES ('offset',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(ident+1,))
                conn.commit()
        except Exception:
            logging.exception("WEEX bot loop failed")
        time.sleep(3)
if __name__=="__main__":main()
