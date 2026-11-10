"""WEEX pilot candidate gate; authenticated read only. No leverage or order changes."""
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
audit=json.loads((ROOT/"live_1x_minimum_audit_latest.json").read_text(encoding="utf-8"))
positions=query("/capi/v3/account/position/allPosition")
orders=query("/capi/v3/openOrders?limit=100&page=0")
if not isinstance(positions,list) or not isinstance(orders,list):raise RuntimeError("Account data invalid")
busy={o.get("symbol") for o in positions+orders}
candidate=[]
for r in audit["symbols"]:
 if r.get("indicativeWithin5USDT") is not True or r["symbol"] in busy:continue
 c=query("/capi/v3/account/symbolConfig?symbol="+r["symbol"])
 if isinstance(c,list):c=next((x for x in c if x.get("symbol")==r["symbol"]),{})
 candidate.append({"symbol":r["symbol"],"indicativeMinNotionalUSDT":r.get("indicativeMinNotionalUSDT"),
 "crossMode":c.get("marginType") in ("CROSS","CROSSED"),"currentCrossLeverage":c.get("crossLeverage"),
 "pilotReady":False,"blockers":["LIVE_1X_NOT_CONFIGURED","CLOSE_ONLY_UNVERIFIED","EXCHANGE_ORDER_MINIMUM_UNVERIFIED"]})
report={"checkedAt":datetime.now(timezone.utc).isoformat(),"accountPositions":len(positions),
"openOrders":len(orders),"eligibleIndicativePairs":len(candidate),"candidates":candidate,
"livePilotGo":False,"exchangeWrites":False}
p=ROOT/"live_1x_selected_candidates_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(report,indent=2),encoding="utf-8");t.replace(p)
print("candidate_count",len(candidate),"pairs",[(x["symbol"],x["currentCrossLeverage"]) for x in candidate],"pilotGO",False)
