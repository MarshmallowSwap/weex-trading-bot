"""Safe read-only WEEX end-to-end reconciliation inventory."""
import json,sqlite3
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
from weex_order_pagination import history
from monitor import query
ROOT=Path(__file__).resolve().parent
def run():
 hist=history(max_pages=5)
 opened=query("/capi/v3/openOrders?limit=100&page=0")
 if not isinstance(opened,list):raise ValueError("Open-order schema unavailable")
 all_orders=hist["orders"]+opened
 db_path=ROOT/"execution_intents.sqlite3"
 bindings=[]
 if db_path.exists():
  with closing(sqlite3.connect(db_path)) as db:
   tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   if "client_bindings" in tables:
    bindings=db.execute("SELECT intent_id,client_id FROM client_bindings").fetchall()
 reports=[]
 for intent,client in bindings:
  matches=[o for o in all_orders if str(o.get("clientOrderId") or "")==client]
  ids={str(o.get("orderId")) for o in matches}
  reports.append({"intentId":intent,"matchedExchangeOrders":len(ids),
    "state":"MATCHED" if len(ids)==1 else "UNRESOLVED"})
 result={"checkedAt":datetime.now(timezone.utc).isoformat(),"historicalOrders":len(hist["orders"]),
 "openOrders":len(opened),"boundIntents":len(bindings),"matches":reports,
 "sourcePaginationBounded":hist["completeWithinRequestedBounds"],"liveExecutionEnabled":False,
 "note":"Inventory only; does not claim full historical coverage or update orders."}
 target=ROOT/"weex_e2e_reconciliation_latest.json"
 temp=target.with_suffix(".tmp");temp.write_text(json.dumps(result,indent=2),encoding="utf-8");temp.replace(target)
 return result
if __name__=="__main__":
 r=run()
 print("history",r["historicalOrders"],"open",r["openOrders"],"bound",r["boundIntents"],"matches",len(r["matches"]))
