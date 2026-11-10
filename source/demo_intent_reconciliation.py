"""Read-only reconciliation of persisted demo intents with exchange history.
Never retries an uncertain order; cannot submit live or demo orders.
"""
import json,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from contextlib import closing
from monitor import query
from demo_intent_binding import DB
from verified_order_state_sync import validate
ROOT=Path(__file__).resolve().parent
def audit(records,db_path=DB):
 if not isinstance(records,list):return {"certified":False,"reason":"INVALID_HISTORY","intents":[]}
 if not Path(db_path).exists():return {"certified":False,"reason":"NO_REGISTERED_INTENTS","intents":[],"ordersSubmitted":False}
 with closing(sqlite3.connect(db_path)) as c:
  bindings=[{"clientId":a,"symbol":b,"state":d,"orderId":e} for a,b,d,e in c.execute("SELECT client_id,symbol,state,exchange_id FROM demo_intents")]
 output=[]
 for b in bindings:
  verdict=validate(b["clientId"],records)
  output.append({"clientId":b["clientId"],"state":b["state"],"verified":verdict["verified"],"exchangeId":verdict.get("orderId"),"action":"DO_NOT_RESUBMIT"})
 return {"certified":bool(output) and all(x["verified"] for x in output),
         "intents":output,"ordersSubmitted":False}
def run():
 orders=query("/capi/v3/sim/order/history?symbol=BTCSUSDT&limit=100&page=0")
 result=audit(orders)
 result["checkedAt"]=datetime.now(timezone.utc).isoformat()
 (ROOT/"demo_intent_reconciliation_latest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 return result
if __name__=="__main__":
 r=run();print("demo intents",len(r["intents"]),"verified",r["certified"],"orders submitted",r["ordersSubmitted"])
