"""WEEX Futures wallet-only read-only notifications.
This service uses an isolated SQLite cursor and skips historic executions at first boot.
"""
import base64,hashlib,hmac,json,logging,sqlite3,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CREDS=ROOT/"weex_credentials.json"
TG=Path(r"D:\FUNDSHOT\hyperliquid_alerts\config.json")
DB=ROOT/"events.sqlite3"
logging.basicConfig(filename=str(ROOT/"monitor.log"),level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
def query(path):
 c=json.loads(CREDS.read_text(encoding="utf-8"))
 ts=str(int(time.time()*1000))
 sig=base64.b64encode(hmac.new(c["secret_key"].encode(),
       (ts+"GET"+path).encode(),hashlib.sha256).digest()).decode()
 h={"ACCESS-KEY":c["api_key"],"ACCESS-SIGN":sig,
    "ACCESS-PASSPHRASE":c["passphrase"],"ACCESS-TIMESTAMP":ts,
    "Content-Type":"application/json"}
 req=urllib.request.Request("https://api-contract.weex.com"+path,headers=h)
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
def trades():
 response=query("/capi/v3/userTrades?limit=100")
 if not isinstance(response,list):raise ValueError("Unexpected trades response")
 return sorted(response,key=lambda v:(int(v.get("time") or 0),str(v.get("id",""))))
def direction(t):
 position=str(t.get("positionSide","")).upper()
 side=str(t.get("side","")).upper()
 opening=(position=="LONG" and side=="BUY") or (position=="SHORT" and side=="SELL")
 closing=(position=="LONG" and side=="SELL") or (position=="SHORT" and side=="BUY")
 return ("open" if opening else "close" if closing else "unknown"),position
def send(t,cfg):
 from sys import path
 path.insert(0,r"D:\FUNDSHOT\hyperliquid_alerts")
 from photo import send_photo
 action,side=direction(t)
 symbol=str(t.get("symbol","?"))
 pnl=float(t.get("realizedPnl") or 0)
 if action=="open":kind="long" if side=="LONG" else "short"
 elif action=="close" and pnl!=0:kind="profit" if pnl>0 else "loss"
 else:kind=None
 info=(f"WEEX FUTURES | {action.upper()} {side}\n"
       f"{symbol}\nPrice: {t.get('price')}\nSize: {t.get('qty')}\n"
       f"Realized PnL: {pnl:+.4f} USDT\n"
       f"Execution ID: {t.get('id')}")
 if kind:
  fields=([("COIN",symbol),("ENTRY",t.get("price","N/D")),
           ("SIZE",str(t.get("qty","N/D"))),("LEVA","N/D"),
           ("ORA",time.strftime("%H:%M UTC",time.gmtime(int(t.get("time") or 0)/1000)))]
          if action=="open" else
          [("COIN",symbol),("PNL",f"{pnl:+.4f} USDT"),
           ("ROI","N/D"),("EXIT",t.get("price","N/D")),("DURATA","N/D")])
  send_photo(cfg,kind,fields,info+("\nEXIT TYPE: non ancora verificato su WEEX" if action=="close" else ""))
 else:
  body=json.dumps({"chat_id":cfg["telegram_chat_id"],"text":info}).encode()
  req=urllib.request.Request("https://api.telegram.org/bot"+cfg["telegram_bot_token"]+"/sendMessage",body,{"Content-Type":"application/json"})
  with urllib.request.urlopen(req,timeout=20) as r:
   ans=json.load(r)
   if not ans.get("ok"):raise RuntimeError("Telegram send failed")
def main():
 conn=sqlite3.connect(DB)
 conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
 conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
 conn.commit()
 print("WEEX read-only watcher started",flush=True)
 while True:
  try:
   current=trades()
   already=conn.execute("SELECT value FROM state WHERE key='initialized'").fetchone()
   if not already:
    for t in current:conn.execute("INSERT OR IGNORE INTO events VALUES (?,?)",(str(t["id"]),"baseline"))
    conn.execute("INSERT OR REPLACE INTO state VALUES ('initialized','1')")
    conn.commit()
    logging.info("WEEX baseline initialized (%d executions)",len(current))
   else:
    cfg=json.loads(TG.read_text(encoding="utf-8"))
    for t in current:
     ident=str(t["id"])
     if conn.execute("SELECT 1 FROM events WHERE id=?",(ident,)).fetchone():continue
     send(t,cfg)
     conn.execute("INSERT OR IGNORE INTO events VALUES (?,?)",(ident,"sent"))
     conn.commit()
   print("WEEX heartbeat count",len(current),flush=True)
  except Exception:
   logging.exception("WEEX polling error")
  time.sleep(12)
if __name__=="__main__":main()
