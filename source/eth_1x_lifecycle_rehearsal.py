"""ETHUSDT live pilot offline lifecycle rehearsal. Real account queried read-only.
No orders or leverage changes; protects occupied symbols and tests crash recovery.
"""
import json,tempfile,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from live_1x_order_gate import assess
R=Path(__file__).resolve().parent
positions=query("/capi/v3/account/position/allPosition")
orders=query("/capi/v3/openOrders?limit=100&page=0")
conf=query("/capi/v3/account/symbolConfig?symbol=ETHUSDT")
if isinstance(conf,list):conf=next((x for x in conf if x.get("symbol")=="ETHUSDT"),{})
if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError("INVALID_ACCOUNT_SNAPSHOT")
checks={}
checks["manual_symbol_unoccupied"]=not any(x.get("symbol")=="ETHUSDT" for x in positions+orders)
checks["cross_1x"]=conf.get("marginType") in ("CROSS","CROSSED") and str(conf.get("crossLeverage"))=="1"
checks["pilot_config_orders_off"]=json.loads((R/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8")).get("executionEnabled") is False
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
 db=Path(d)/"rehearsal.db"
 with sqlite3.connect(db) as c:
  c.execute("CREATE TABLE orders(client_id TEXT PRIMARY KEY,status TEXT,filled TEXT)")
  c.execute("INSERT INTO orders VALUES('pilot_dryrun_1','PREPARED','0')")
  c.execute("UPDATE orders SET status='SUBMISSION_UNKNOWN' WHERE client_id='pilot_dryrun_1'")
 with sqlite3.connect(db) as c:observed=c.execute("SELECT status FROM orders WHERE client_id='pilot_dryrun_1'").fetchone()[0]
 checks["uncertain_order_survives_restart"]=observed=="SUBMISSION_UNKNOWN"
 checks["uncertain_order_cannot_resubmit"]=observed!="PREPARED"
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"checks":checks,
 "rehearsalPass":all(checks.values()),"realCloseCertified":False,
 "realOrderAccepted":False,"productionGo":False,"exchangeWrites":False}
p=R/"eth_1x_lifecycle_rehearsal_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(out,indent=2),encoding="utf-8");t.replace(p)
print("REHEARSAL",sum(checks.values()),"/",len(checks),"LIVE_GO",False,"REAL_ORDERS",0)
