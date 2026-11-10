from pathlib import Path
from datetime import datetime
r=Path(r"D:\FUNDSHOT")
m=r/"weex_alerts"/"monitor.py"
s=r/"weex_alerts"/"send_open_snapshot.py"
c=r/"hyperliquid_alerts"/"cards.py"
tag=datetime.now().strftime("%Y%m%d_%H%M%S")
for p in (m,s,c):p.with_name(p.stem+".backup_"+tag+p.suffix).write_bytes(p.read_bytes())
data=m.read_text(encoding="utf-8")
old=''' info=(f"WEEX FUTURES | {action.upper()} {side}\\n"
       f"{symbol}\\nPrice: {t.get('price')}\\nSize: {t.get('qty')}\\n"
       f"Realized PnL: {pnl:+.4f} USDT\\n"
       f"Execution ID: {t.get('id')}")'''
new=''' info=(f"{'🟢' if side=='LONG' else '🔴'} WEEX FUTURES | {action.upper()} {side}\\n"
       f"━━━━━━━━━━━━━━━━━━\\n"
       f"💠 {symbol}\\n"
       f"🎯 Prezzo: {t.get('price')} USDT\\n"
       f"📦 Quantità: {t.get('qty')}\\n"
       f"🕒 UTC: {time.strftime('%H:%M',time.gmtime(int(t.get('time') or 0)/1000))}\\n"
       + (f"💰 PnL realizzato: {pnl:+.4f} USDT\\n" if action=='close' else "")
       + f"🔎 Esecuzione: {t.get('id')}")'''
assert old in data
m.write_text(data.replace(old,new),encoding="utf-8")
data=s.read_text(encoding="utf-8")
data=data.replace(' pnl=Decimal(str(x.get("unrealizePnl") or 0))\n','')
data=data.replace(''' caption=(f"WEEX | SNAPSHOT POSIZIONE APERTA (non una nuova apertura)\\n"
          f"{symbol} {side} | Leva {lev} | {x.get('marginType','')}\\n"
          f"Entry media: {entry:.2f} USDT | Size: {size}\\n"
          f"PnL non realizzato all'istante della lettura: {pnl:+.5f} USDT\\n"
          f"Liquidazione indicativa API: {x.get('liquidatePrice','N/D')} USDT")''',
''' caption=(f"📸 WEEX | SNAPSHOT POSIZIONE APERTA\\n"
          f"━━━━━━━━━━━━━━━━━━\\n"
          f"{'🟢' if side=='LONG' else '🔴'} {symbol} | {side} {lev}\\n"
          f"🎯 Entry medio: {entry:.2f} USDT\\n"
          f"📦 Size: {size}\\n"
          f"🛡️ Margine: {x.get('marginType','N/D')}\\n"
          f"⚠️ Prezzo liquidazione: {x.get('liquidatePrice','N/D')} USDT\\n"
          f"ℹ️ Snapshot di posizione esistente, non una nuova apertura.")''')
data=data.replace(',"UNREALIZED_PNL",pnl','')
assert "PnL non realizzato" not in data and 'UNREALIZED_PNL' not in data
s.write_text(data,encoding="utf-8")
data=c.read_text(encoding="utf-8")
data=data.replace('FONT_BOLD = r"C:\\Windows\\Fonts\\arialbd.ttf"','FONT_BOLD = r"C:\\Windows\\Fonts\\arialbd.ttf"')
# Keep strict value slots with fitted larger type, stronger contrast and subtle colored outlines.
data=data.replace('''        margin=3
        draw.rounded_rectangle((l+margin,t+margin,r-margin,b-margin),
                               radius=7,fill=(2,10,19,184))
        write_fitted(draw,value,(l+margin+2,t+margin+2,r-margin-2,b-margin-2),
                     color_for(kind,str(label).upper(),value),
                     maximum=24 if kind=="winrate" else 31)''',
'''        margin=2
        color=color_for(kind,str(label).upper(),value)
        accent={"long":(34,238,146),"short":(255,79,113),
                "profit":(36,237,150),"loss":(255,80,99),
                "pnl":(239,184,71),"winrate":(55,180,255)}[kind]
        draw.rounded_rectangle((l+margin,t+margin,r-margin,b-margin),
                               radius=10,fill=(2,10,22,238),
                               outline=(*accent,220),width=2)
        write_fitted(draw,value,(l+margin+3,t+margin+3,r-margin-3,b-margin-3),
                     color,maximum=27 if kind=="winrate" else 35)''')
c.write_text(data,encoding="utf-8")
print("PATCH_APPLIED",tag)
