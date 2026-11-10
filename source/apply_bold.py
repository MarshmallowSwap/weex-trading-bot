from pathlib import Path
from datetime import datetime
root=Path(r"D:\FUNDSHOT")
photo=root/"hyperliquid_alerts"/"photo.py"
mon=root/"weex_alerts"/"monitor.py"
snap=root/"weex_alerts"/"send_open_snapshot.py"
stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
for p in (photo,mon,snap):p.with_name(p.stem+".pre_bold_"+stamp+p.suffix).write_bytes(p.read_bytes())
p=photo
t=p.read_text(encoding="utf-8")
assert 'part("caption",caption[:1000])+' in t
t=t.replace('part("caption",caption[:1000])+','part("caption",caption[:1000])+part("parse_mode","HTML")+')
p.write_text(t,encoding="utf-8")
p=snap
t=p.read_text(encoding="utf-8")
t=t.replace('from pathlib import Path','from pathlib import Path\nfrom html import escape')
a=t.index(' caption=(f"📸 WEEX')
b=t.index('\n send_photo(',a)
t=t[:a]+''' caption=(f"📸 <b>WEEX | SNAPSHOT POSIZIONE APERTA</b>\\n"
          f"━━━━━━━━━━━━━━━━━━\\n"
          f"{'🟢' if side=='LONG' else '🔴'} <b>{escape(symbol)} | {escape(side)} {escape(lev)}</b>\\n"
          f"🎯 Entry medio: <b>{entry:.2f} USDT</b>\\n"
          f"📦 Quantità: <b>{size}</b>\\n"
          f"🛡️ Margine: {escape(str(x.get('marginType','N/D')))}\\n"
          f"⚠️ Liquidazione: <b>{escape(str(x.get('liquidatePrice','N/D')))} USDT</b>\\n"
          f"ℹ️ Snapshot posizione esistente, non una nuova apertura.")'''+t[b:]
p.write_text(t,encoding="utf-8")
p=mon
t=p.read_text(encoding="utf-8")
t=t.replace('import base64,hashlib,hmac,json,logging,sqlite3,time,urllib.request','import base64,hashlib,hmac,json,logging,sqlite3,time,urllib.request\nfrom html import escape')
a=t.index(' info=(f"',t.index('def send(t,cfg):'))
b=t.index('\n if kind:',a)
t=t[:a]+''' info=(f"{'🟢' if side=='LONG' else '🔴'} <b>WEEX FUTURES | {action.upper()} {escape(side)}</b>\\n"
       f"━━━━━━━━━━━━━━━━━━\\n"
       f"💠 <b>{escape(symbol)}</b>\\n"
       f"🎯 Prezzo: <b>{escape(str(t.get('price')))} USDT</b>\\n"
       f"📦 Quantità: <b>{escape(str(t.get('qty')))}</b>\\n"
       f"🕒 UTC: {time.strftime('%H:%M',time.gmtime(int(t.get('time') or 0)/1000))}\\n"
       + (f"💰 PnL realizzato: <b>{pnl:+.4f} USDT</b>\\n" if action=='close' else "")
       + f"🔎 Esecuzione: {escape(str(t.get('id')))}")'''+t[b:]
t=t.replace('info+("\\nEXIT TYPE: "+exit_type if exit_type else "")','info+("\\nEXIT TYPE: <b>"+escape(exit_type)+"</b>" if exit_type else "")')
t=t.replace('{"chat_id":cfg["telegram_chat_id"],"text":info}','{"chat_id":cfg["telegram_chat_id"],"text":info,"parse_mode":"HTML"}')
p.write_text(t,encoding="utf-8")
print("BOLD_FORMAT_PATCH_OK")
