"""WEEX 1x LIVE pilot preflight, read-only; excludes every symbol with existing exposure."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))
positions=query("/capi/v3/account/position/allPosition")
orders=query("/capi/v3/openOrders?limit=100&page=0")
if not isinstance(positions,list) or not isinstance(orders,list):raise RuntimeError("UNEXPECTED_ACCOUNT_SCHEMA")
reserved={str(x.get("symbol")) for x in positions if x.get("symbol")}
reserved|={str(x.get("symbol")) for x in orders if x.get("symbol")}
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"existingPositionCount":len(positions),
 "existingOpenOrders":len(orders),"excludedSymbols":sorted(reserved),
 "pilotLeverage":cfg["leverage"],"maxAdditionalNotionalUSDT":cfg["maxAdditionalNotionalUSDT"],
 "closeOnlyVerified":False,"pilotOrderPermitted":False,"exchangeWrites":False}
dest=ROOT/"live_1x_pilot_preflight_latest.json"
dest.write_text(json.dumps(out,indent=2),encoding="utf-8")
print("PILOT NO_GO positions",len(positions),"open_orders",len(orders),"excluded_symbols",len(reserved),"writes",False)
