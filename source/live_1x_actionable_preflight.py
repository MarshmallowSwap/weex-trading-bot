"""Live 1x pilot readiness with separately verifiable evidence, READ ONLY.
No order requests, no leverage change. Produces honest blockers rather than hardcoded GO.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from live_1x_order_gate import assess
ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))
candidates=json.loads((ROOT/"live_1x_selected_candidates_latest.json").read_text(encoding="utf-8"))["candidates"]
positions=query("/capi/v3/account/position/allPosition")
orders=query("/capi/v3/openOrders?limit=100&page=0")
if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError("ACCOUNT_UNAVAILABLE")
status=[]
for c in candidates:
 symbol=c["symbol"]
 try:
  raw=query("/capi/v3/account/symbolConfig?symbol="+symbol)
  if isinstance(raw,list):raw=next((r for r in raw if r.get("symbol")==symbol),{})
  if not isinstance(raw,dict):raise ValueError("INVALID_CONFIG")
  mode=raw.get("marginType")
  leverage=raw.get("crossLeverage")
  technical=assess(symbol=symbol,positions=positions,open_orders=orders,
   account_mode=mode,configured_leverage=leverage,
   min_notional=c.get("indicativeMinNotionalUSDT"),requested_notional="5",
   close_procedure_verified=False,reduce_only_verified=False,client_order_binding_verified=False,
   execution_enabled=cfg.get("executionEnabled",False))
  status.append({"symbol":symbol,"crossLeverage":leverage,"mode":mode,
                 "blockingChecks":technical["blockers"]+["ORDER_SIZE_ACCEPTANCE_NOT_PROVEN"],
                 "pilotPermitted":False})
 except Exception as e:status.append({"symbol":symbol,"pilotPermitted":False,"blockingChecks":[type(e).__name__]})
report={"checkedAt":datetime.now(timezone.utc).isoformat(),"environment":"LIVE_READ_ONLY_PRECHECK",
"positions":len(positions),"openOrders":len(orders),"candidates":status,
"pilotGo":False,"ordersSubmitted":False,"manualPositionsUntouched":True}
p=ROOT/"live_1x_actionable_preflight_latest.json";temp=p.with_suffix(".tmp")
temp.write_text(json.dumps(report,indent=2),encoding="utf-8");temp.replace(p)
print("PRECHECK NO_GO","candidates",len(status),"already1x",sum(x.get("crossLeverage")=="1" for x in status))
print("blockers",sorted(set(y for x in status for y in x["blockingChecks"])))
