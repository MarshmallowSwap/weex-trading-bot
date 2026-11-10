"""Idempotent agent-watch watchdog; reports failures and recovery only."""
import json,sqlite3,urllib.request
from pathlib import Path
from agent_health import assess
ROOT=Path(__file__).resolve().parent
DB=ROOT/"agent_watchdog.sqlite3"
def init(db):
 db.execute("CREATE TABLE IF NOT EXISTS watch (id TEXT PRIMARY KEY,status TEXT,consecutive INTEGER NOT NULL,last_notified TEXT)")
def transition(db,status):
 init(db)
 row=db.execute("SELECT status,consecutive,last_notified FROM watch WHERE id='market_diagnostics'").fetchone()
 old,n,notified=row if row else (None,0,None)
 n=(n+1) if status in ("ERROR","STALE") else 0
 event=None
 if status in ("ERROR","STALE") and n>=2 and notified!=status:event=status
 if status=="OK" and notified in ("ERROR","STALE"):event="RECOVERED"
 db.execute("INSERT INTO watch VALUES ('market_diagnostics',?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,consecutive=excluded.consecutive",(status,n,notified))
 return event,n
def send_telegram(message):
 from monitor import TG
 cfg=json.loads(TG.read_text(encoding="utf-8"))
 req=urllib.request.Request("https://api.telegram.org/bot"+cfg["telegram_bot_token"]+"/sendMessage",
  json.dumps({"chat_id":cfg["telegram_chat_id"],"text":message}).encode(),{"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=15) as resp:
  if not json.load(resp).get("ok"):raise RuntimeError("Telegram rejected message")
def run(send=False):
 state=assess()
 with sqlite3.connect(DB) as db:event,n=transition(db,state["status"])
 delivered=False
 if event and send:
  send_telegram("WEEX AI DIAGNOSTICS "+event+" | "+state["reason"])
  with sqlite3.connect(DB) as db:
   db.execute("UPDATE watch SET last_notified=? WHERE id='market_diagnostics'",("OK" if event=="RECOVERED" else event,))
  delivered=True
 return {"state":state["status"],"consecutive":n,"event":event,"delivered":delivered}
if __name__=="__main__":print(json.dumps(run(send=True)))
