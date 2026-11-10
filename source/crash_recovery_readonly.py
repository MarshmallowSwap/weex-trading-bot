"""Crash-recovery preflight, read-only. Fail closed on missing/double matched orders."""
import sqlite3,json
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
from verified_order_state_sync import validate
ROOT=Path(__file__).resolve().parent
def assess(bindings,records,history_complete):
 issues=[]
 if not history_complete:issues.append("INCOMPLETE_EXCHANGE_HISTORY")
 client_ids=[x["client_id"] for x in bindings]
 if len(client_ids)!=len(set(client_ids)):issues.append("DUPLICATE_BINDING")
 seen_exchange={}
 for b in bindings:
  o=validate(b["client_id"],records)
  if not o["verified"]:
   issues.append(b["intent_id"]+":"+o["reason"])
   continue
  if o["orderId"] in seen_exchange:issues.append("SHARED_EXCHANGE_ORDER_ID")
  seen_exchange[o["orderId"]]=b["intent_id"]
 return {"canResume":not issues and len(bindings)>0,"issues":issues,
         "boundIntents":len(bindings),"validatedOrders":len(seen_exchange),
         "exchangeWrites":False}
def run():
 from weex_order_pagination import history
 from monitor import query
 h=history(max_pages=5)
 opened=query("/capi/v3/openOrders?limit=100&page=0")
 if not isinstance(opened,list):raise ValueError("INVALID_OPEN_ORDERS")
 db=ROOT/"execution_intents.sqlite3"
 bindings=[]
 if db.exists():
  with closing(sqlite3.connect(db)) as c:
   tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   if "client_bindings" in tables:
    bindings=[{"intent_id":i,"client_id":c} for i,c in c.execute("SELECT intent_id,client_id FROM client_bindings")]
 result=assess(bindings,h["orders"]+opened,h["completeWithinRequestedBounds"])
 result.update({"checkedAt":datetime.now(timezone.utc).isoformat(),"recoveryCertified":False,
                "reason":"Read-only matching is not a crash-and-restart exchange-order test"})
 p=ROOT/"crash_recovery_readonly_latest.json";t=p.with_suffix(".tmp")
 t.write_text(json.dumps(result,indent=2),encoding="utf-8");t.replace(p)
 return result
if __name__=="__main__":
 d=run();print("resume",d["canResume"],"bound",d["boundIntents"],"verified",d["validatedOrders"],"issues",d["issues"])
