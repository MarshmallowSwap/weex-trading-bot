import sys,json,time
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import query
sys.path.insert(0,r"D:\FUNDSHOT\hyperliquid_alerts")
from photo import send_photo
p=query("/capi/v3/account/position/allPosition")
valid=[x for x in p if Decimal(str(x.get("size") or 0))>0 and str(x.get("side","")).upper() in ("LONG","SHORT")]
if not valid:
 print("NO_OPEN_POSITIONS")
 raise SystemExit(0)
cfg=json.loads(Path(r"D:\FUNDSHOT\hyperliquid_alerts\config.json").read_text(encoding="utf-8"))
for x in valid:
 symbol=x["symbol"];side=x["side"].upper()
 size=Decimal(str(x["size"])); value=Decimal(str(x["openValue"]))
 entry=value/size if size else Decimal("0")
 lev=str(x.get("leverage","N/D"))+"x"
 pnl=Decimal(str(x.get("unrealizePnl") or 0))
 fields=[("COIN",symbol),("ENTRY",f"{entry:,.2f}"),("SIZE",str(size)),
         ("LEVA",lev),("ORA",time.strftime("%H:%M UTC",time.gmtime(int(x.get("createdTime",0))/1000)))]
 caption=(f"WEEX | SNAPSHOT POSIZIONE APERTA (non una nuova apertura)\n"
          f"{symbol} {side} | Leva {lev} | {x.get('marginType','')}\n"
          f"Entry media: {entry:.2f} USDT | Size: {size}\n"
          f"PnL non realizzato all'istante della lettura: {pnl:+.5f} USDT\n"
          f"Liquidazione indicativa API: {x.get('liquidatePrice','N/D')} USDT")
 send_photo(cfg,"long" if side=="LONG" else "short",fields,caption)
 print("SNAPSHOT_SENT",symbol,side,"LEVERAGE",lev,"ENTRY",entry,"UNREALIZED_PNL",pnl)
