"""Single authoritative WEEX 1x pilot preflight; READ ONLY. Never submits orders.
Prevents activating on stale evidence, preexisting manual exposure, or unverified exit.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from live_1x_order_gate import assess
ROOT=Path(__file__).resolve().parent
def evaluate(snapshot, candidates, pilot):
 issues=[]
 if pilot.get("executionEnabled") is not False or pilot.get("liveOrderSubmissionAllowed") is not False:issues.append("PILOT_WRITE_FLAG_ENABLED")
 if snapshot.get("positions") is None or snapshot.get("open_orders") is None:issues.append("ACCOUNT_UNAVAILABLE")
 checks=[]
 for item in candidates:
  r=assess(symbol=item["symbol"],positions=snapshot.get("positions"),open_orders=snapshot.get("open_orders"),
   account_mode=item.get("marginType"),configured_leverage=item.get("crossLeverage"),
   min_notional=item.get("indicativeMinNotionalUSDT"),
   close_procedure_verified=False,reduce_only_verified=False,client_order_binding_verified=False)
  checks.append({"symbol":item["symbol"],"eligible":False,"blockers":r["blockers"]+["INDICATIVE_MINIMUM_NOT_EXCHANGE_CERTIFIED"]})
 return {"go":False,"reason":"CLOSING_AND_ORDER_PROVENANCE_NOT_CERTIFIED","issues":issues,"candidates":checks,"writes":False}
def run():
 pilot=json.loads((ROOT/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))
 source=json.loads((ROOT/"live_1x_selected_candidates_latest.json").read_text(encoding="utf-8"))
 positions=query("/capi/v3/account/position/allPosition")
 opened=query("/capi/v3/openOrders?limit=100&page=0")
 if not isinstance(positions,list) or not isinstance(opened,list):raise ValueError("INVALID_ACCOUNT_RESPONSE")
 result=evaluate({"positions":positions,"open_orders":opened},[
  {"symbol":c["symbol"],"marginType":"CROSSED" if c.get("crossMode") else None,
   "crossLeverage":c.get("currentCrossLeverage"),"indicativeMinNotionalUSDT":c.get("indicativeMinNotionalUSDT")}
  for c in source["candidates"]],pilot)
 result.update({"at":datetime.now(timezone.utc).isoformat(),"positionsCount":len(positions),"openOrdersCount":len(opened)})
 target=ROOT/"pilot_1x_integrated_preflight_latest.json";tmp=target.with_suffix(".tmp")
 tmp.write_text(json.dumps(result,indent=2),encoding="utf-8");tmp.replace(target)
 return result
if __name__=="__main__":
 x=run();print("PILOT","GO" if x["go"] else "NO_GO","positions",x["positionsCount"],"candidates",len(x["candidates"]),"exchange_writes",x["writes"])
