from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\commands.py")
s=p.read_text(encoding="utf-8")
s=s.replace("from agents_status import status as agent_status","from agents_status import status as agent_status\nfrom telegram_ai_fullmenu import summary as full_summary,menu as full_menu,positions_menu,set_positions,sl_menu,set_sl")
s=s.replace('if choice=="aitp:custom":','''if choice=="aimenu:home":
                                api(token,"sendMessage",{"chat_id":chat,"text":full_summary(),"reply_markup":full_menu()})
                            elif choice=="aimenu:tp":
                                api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":ai_keyboard()})
                            elif choice=="aimenu:positions":
                                api(token,"sendMessage",{"chat_id":chat,"text":"📊 Scegli il massimo di posizioni (1–10):","reply_markup":positions_menu()})
                            elif choice=="aimenu:sl":
                                api(token,"sendMessage",{"chat_id":chat,"text":"🛑 SL attualmente OFF. L'opzione futura richiederà prezzo/modalità e verifica del rischio.","reply_markup":sl_menu()})
                            elif choice.startswith("aipos:"):
                                n=set_positions(choice.split(":")[1])
                                api(token,"sendMessage",{"chat_id":chat,"text":f"✅ Limite configurato: {n} posizioni. Nessun ordine eseguito.","reply_markup":full_menu()})
                            elif choice=="aisl:off":
                                set_sl(False)
                                api(token,"sendMessage",{"chat_id":chat,"text":"✅ SL confermato OFF. Il trading resta disabilitato.","reply_markup":full_menu()})
                            elif choice=="aisl:info":
                                api(token,"sendMessage",{"chat_id":chat,"text":"SL configurabile in futuro: prezzo fisso, percentuale, ATR o trailing. Nessuno stop protettivo viene inserito ora."})
                            elif choice=="aitp:custom":''')
s=s.replace('api(token,"sendMessage",{"chat_id":chat,"text":ai_message(),"reply_markup":ai_keyboard()})\n                    elif from_id==allowed_user', 'api(token,"sendMessage",{"chat_id":chat,"text":full_summary(),"reply_markup":full_menu()})\n                    elif from_id==allowed_user')
p.with_suffix(".py.bak_full_settings").write_text(p.read_text(encoding="utf-8"),encoding="utf-8")
p.write_text(s,encoding="utf-8")
