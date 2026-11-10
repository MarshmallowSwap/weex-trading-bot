from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\commands.py")
s=p.read_text(encoding="utf-8")
assert 'from telegram_ai_settings import' not in s
s=s.replace('from decimal import Decimal','from decimal import Decimal\nfrom telegram_ai_settings import message as ai_message, keyboard as ai_keyboard, save_profit as ai_save_profit, validate as ai_validate')
s=s.replace('    conn.commit()\n    while True:',"""    conn.execute("CREATE TABLE IF NOT EXISTS input_state(chat_id TEXT PRIMARY KEY, mode TEXT NOT NULL)")
    conn.commit()
    while True:""")
s=s.replace('"allowed_updates":["message"]','"allowed_updates":["message","callback_query"]')
needle='                m=update.get("message",{})'
replacement='''                callback=update.get("callback_query")
                if callback:
                    m=callback.get("message") or {}
                    callback_chat=str(m.get("chat",{}).get("id"))
                    callback_from=str(callback.get("from",{}).get("id"))
                    allowed_user=str(cfg.get("telegram_user_id") or chat)
                    if callback_chat==chat and callback_from==allowed_user:
                        choice=str(callback.get("data") or "")
                        try:
                            if choice=="aitp:custom":
                                conn.execute("INSERT INTO input_state VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET mode=excluded.mode",(chat,"await_custom_tp"))
                                conn.commit()
                                api(token,"sendMessage",{"chat_id":chat,"text":"✏️ Invia il profitto netto desiderato in USDT (es. 1,75). /cancel per annullare."})
                            elif choice=="aitp:show":
                                api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":ai_keyboard()})
                            elif choice.startswith("aitp:"):
                                val=choice.partition(":")[2]
                                if val in ("0.50","1.00","2.00","5.00"):
                                    amount=ai_save_profit(val)
                                    api(token,"sendMessage",{"chat_id":chat,"text":f"✅ TP configurato: +{amount:.2f} USDT netti oltre Break Even. Non sono stati inviati ordini."})
                        except Exception:
                            logging.exception("WEEX AI TP callback failed")
                            api(token,"sendMessage",{"chat_id":chat,"text":"Impossibile aggiornare il TP."})
                    try:
                        api(token,"answerCallbackQuery",{"callback_query_id":callback["id"]})
                    except Exception: logging.exception("Telegram callback acknowledge failed")
                    conn.execute("INSERT INTO cursor VALUES ('offset',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(ident+1,))
                    conn.commit()
                    continue
                m=update.get("message",{})'''
assert needle in s
s=s.replace(needle,replacement)
s=s.replace('                if str(m.get("chat",{}).get("id"))==chat:\n','''                if str(m.get("chat",{}).get("id"))==chat:
                    from_id=str(m.get("from",{}).get("id"))
                    allowed_user=str(cfg.get("telegram_user_id") or chat)
                    if command=="/settings" and from_id==allowed_user:
                        api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":ai_keyboard()})
                    elif from_id==allowed_user and command=="/cancel":
                        conn.execute("DELETE FROM input_state WHERE chat_id=?",(chat,))
                        api(token,"sendMessage",{"chat_id":chat,"text":"Inserimento TP annullato."})
                    elif from_id==allowed_user and conn.execute("SELECT mode FROM input_state WHERE chat_id=?",(chat,)).fetchone()==("await_custom_tp",):
                        try:
                            amount=ai_save_profit(str(m.get("text","")))
                            conn.execute("DELETE FROM input_state WHERE chat_id=?",(chat,))
                            api(token,"sendMessage",{"chat_id":chat,"text":f"✅ TP personalizzato: +{amount:.2f} USDT netti oltre Break Even. Nessun ordine inviato."})
                        except ValueError as e:
                            api(token,"sendMessage",{"chat_id":chat,"text":str(e)+"\\nRiprova oppure /cancel."})
                    elif command in ("/pnl","/winrate"):''')
s=s.replace('                    if command in ("/pnl","/winrate"):\n                        try:', '                        try:')
# check indentation after replace
p.with_suffix(".py.bak_ai_settings").write_text(p.read_text(encoding="utf-8"),encoding="utf-8")
p.write_text(s,encoding="utf-8")
