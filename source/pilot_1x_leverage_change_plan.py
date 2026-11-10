"""One-symbol WEEX 1x pilot change plan, no exchange writes."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
R=Path(__file__).resolve().parent
candidates=json.loads((R/"live_1x_selected_candidates_latest.json").read_text(encoding="utf-8"))["candidates"]
positions=query("/capi/v3/account/position/allPosition")
open_orders=query("/capi/v3/openOrders?limit=100&page=0")
if not isinstance(positions,list) or not isinstance(open_orders,list):raise ValueError("INVALID_ACCOUNT_STATE")
busy={x.get("symbol") for x in positions+open_orders}
selected=next((x for x in candidates if x["symbol"]=="ETHUSDT" and x["symbol"] not in busy),None)
if not selected:raise RuntimeError("ETHUSDT_NOT_FREE")
cfg=query("/capi/v3/account/symbolConfig?symbol=ETHUSDT")
if isinstance(cfg,list):cfg=next((x for x in cfg if x.get("symbol")=="ETHUSDT"),{})
if not isinstance(cfg,dict) or cfg.get("marginType") not in ("CROSSED","CROSS"):raise RuntimeError("NOT_CROSS")
report={"at":datetime.now(timezone.utc).isoformat(),"pilotSymbol":"ETHUSDT",
"currentLeverage":cfg.get("crossLeverage"),"requestedLeverage":"1",
"plannedEndpoint":"/capi/v3/account/leverage","method":"POST",
"exchangeChangeExecuted":False,"positionCount":len(positions),
"blockedBusySymbols":sorted(str(x) for x in busy),"orderExecutionEnabled":False,
"reason":"Leverage change plan only; close-only and order lifecycle unverified."}
(R/"pilot_1x_leverage_change_plan_latest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("PILOT_SYMBOL",report["pilotSymbol"],"CROSS_CURRENT",report["currentLeverage"],"REQUESTED",report["requestedLeverage"],"EXCHANGE_CHANGE",False)
