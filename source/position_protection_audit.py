"""WEEX read-only position protection coverage audit, fail closed."""
import json
from pathlib import Path
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
def number(value):
 try:
  x=Decimal(str(value))
  return x if x.is_finite() and x>=0 else None
 except (InvalidOperation,TypeError):return None
def assess(position,algos):
 symbol=position.get("symbol");side=str(position.get("side","")).upper();qty=number(position.get("size"))
 matches=[o for o in algos if o.get("symbol")==symbol and str(o.get("positionSide","")).upper()==side]
 active=[o for o in matches if str(o.get("algoStatus",o.get("status",""))).upper() in ("NEW","OPEN","ACTIVE","UNACTIVATED")]
 if qty is None or side not in ("LONG","SHORT"):
  return {"symbol":symbol,"status":"UNKNOWN","safeToReplace":False}
 return {"symbol":symbol,"side":side,"positionQty":str(qty),"protectionCandidates":len(matches),
         "activeCandidates":len(active),"status":"UNCERTIFIED_COVERAGE","safeToReplace":False,
         "reason":"Algo quantity and position-mode compatibility not independently verified"}
def report():
 positions=query("/capi/v3/account/position/allPosition")
 algos=query("/capi/v3/openAlgoOrders?limit=100&page=1")
 trailing=query("/capi/v3/trailing/openOrders?limit=100&page=0")
 if any(not isinstance(x,list) for x in (positions,algos,trailing)):raise ValueError("Invalid API schema; no report is trusted")
 items=[assess(p,algos+trailing) for p in positions]
 result={"asOf":datetime.now(timezone.utc).isoformat(),"positionCount":len(positions),
         "conditionalOpenCount":len(algos),"trailingOpenCount":len(trailing),
         "positions":items,"algoOrdersFetched":True,"coverageCertified":False,"exchangeModifications":False,
         "limitations":["Conditional orders read page 1 only","Trailing orders read page 0 only","No protective order changes performed"]}
 target=ROOT/"position_protection_audit_latest.json";temp=target.with_suffix(".tmp")
 temp.write_text(json.dumps(result,indent=2),encoding="utf-8");temp.replace(target)
 return result
if __name__=="__main__":
 r=report();print("positions",r["positionCount"],"conditional",r["conditionalOpenCount"],"trailing",r["trailingOpenCount"],"coverageCertified",r["coverageCertified"])
