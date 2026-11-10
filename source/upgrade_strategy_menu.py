from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\telegram_ai_fullmenu.py")
s=p.read_text(encoding="utf-8")
s=s.replace('def tp_modes_menu():','''def select_strategy(kind, mode):
 allowed={"tp":("fixed","dynamic","percent","trailing","hybrid"),"sl":("off","fixed","percent","atr","trailing","ai")}
 if kind not in allowed or mode not in allowed[kind]:raise ValueError("Invalid mode")
 c=load()
 k="tpMode" if kind=="tp" else "slMode"
 if kind=="sl" and mode=="fixed" and not c["strategySettings"].get("fixedStopPrice"):
  raise ValueError("SL prezzo fisso richiede prima un prezzo valido: non selezionato")
 c["strategySettings"][k]=mode
 # SL is a theoretical model setting, never claim protective execution.
 c["risk"]["stopLoss"]["enabled"]=False
 save(c)
 return mode
def tp_modes_menu():''')
for key,label in [("dynamic","Dinamico AI"),("percent","Percentuale netta"),("trailing","Trailing TP"),("hybrid","Ibrido AI")]:
 s=s.replace(label+" · prossimamente",label+" · calcolo")
for key,label in [("percent","Percentuale"),("atr","ATR dinamico"),("trailing","Trailing"),("ai","Dinamico AI"),("fixed","Prezzo fisso")]:
 s=s.replace(label+" · non disponibile",label+" · calcolo")
s=s.replace('f"🛑 Stop Loss: {\'DA CONFIGURARE (non protettivo)\' if sl[\'enabled\'] else \'OFF\'}\\n"','f"🛑 SL modello: {c.get(\'strategySettings\',{}).get(\'slMode\',\'off\').upper()} (non protettivo)\\n"')
s=s.replace('f"🎯 TP netto oltre Break Even: +{Decimal(str(p[\'targetNetProfitUSDT\'])):.2f} USDT\\n"','f"🎯 TP modello: {c.get(\'strategySettings\',{}).get(\'tpMode\',\'fixed\').upper()} | target fisso +{Decimal(str(p[\'targetNetProfitUSDT\'])):.2f} USDT\\n"')
p.write_text(s,encoding="utf-8")
