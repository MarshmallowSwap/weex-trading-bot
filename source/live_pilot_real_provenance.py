"""Real WEEX data, read-only pilot attribution. No orders, no leverage changes."""
import json,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from live_pilot_fill_provenance import verify
R=Path(__file__).resolve().parent
orders=query("/capi/v3/order/history?limit=100&page=0")
fills=query("/capi/v3/userTrades?limit=100")
positions=query("/capi/v3/account/position/allPosition")
if not all(isinstance(x,list) for x in (orders,fills,positions)):raise ValueError("WEEX_DATA_UNAVAILABLE")
db=R/"execution_intents.sqlite3"
bindings=[]
if db.exists():
 with sqlite3.connect(db) as c:
  tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if "client_bindings" in tables:
   bindings=[{"clientOrderId":client,"orderId":None,"state":"UNVERIFIED"} for _,client in c.execute("SELECT intent_id,client_id FROM client_bindings")]
results=[verify(b["clientOrderId"],bindings,orders,fills) for b in bindings]
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"orderHistoryCount":len(orders),
 "tradeCount":len(fills),"openPositionCount":len(positions),"botBindingsObserved":len(bindings),
 "botOrdersVerified":sum(x.get("verified",False) for x in results),
 "positionCloseAuthorized":False,"liveOrderAuthorized":False,"exchangeWrites":False,
 "reason":"Bot identifiers not proven against exchange order IDs and executions"}
p=R/"live_pilot_real_provenance_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(out,indent=2),encoding="utf-8");t.replace(p)
print("REAL_READONLY","orders",len(orders),"trades",len(fills),"positions",len(positions),"bot_bindings",len(bindings),"verified",out["botOrdersVerified"],"writes",False)
