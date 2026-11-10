"""Integrated ETHUSDT 1x read-only verification: live pilot cannot send orders."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
R=Path(__file__).resolve().parent
snap=json.loads((R/"eth_1x_release_snapshot.json").read_text(encoding="utf-8"))
pos=query("/capi/v3/account/position/allPosition")
orders=query("/capi/v3/openOrders?limit=100&page=0")
config=query("/capi/v3/account/symbolConfig?symbol=ETHUSDT")
if isinstance(config,list):config=next((x for x in config if x.get("symbol")=="ETHUSDT"),{})
if not isinstance(pos,list) or not isinstance(orders,list):raise ValueError("INVALID_SNAPSHOT")
checks={"live_symbol_free":not any(x.get("symbol")=="ETHUSDT" for x in pos+orders),
"configured_cross_1x":config.get("marginType") in ("CROSS","CROSSED") and str(config.get("crossLeverage"))=="1",
"pilot_execution_still_off":json.loads((R/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))["executionEnabled"] is False,
"open_order_client_binding_verified":False,
"bot_owned_position_close_verified":False,
"exchange_accepts_5usdt_order":False}
result={"checkedAt":datetime.now(timezone.utc).isoformat(),"checks":checks,
"passed":sum(checks.values()),"total":len(checks),"decision":"NO_GO",
"ordersSubmitted":False,"manualPositionsModified":False}
(R/"eth_1x_integrated_decision_latest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print("PILOT",result["decision"],"checks",result["passed"],"/",result["total"],"manual_positions",len(pos))
