"""Read-only position risk review; rejects unsupported or missing fields."""
from decimal import Decimal,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
import json
ROOT=Path(__file__).resolve().parent
def positive(v):
 try:
  d=Decimal(str(v))
  return d if d.is_finite() and d>0 else None
 except (TypeError,InvalidOperation):return None
def review(p):
 leverage=positive(p.get("leverage"))
 liq=positive(p.get("liquidatePrice"))
 qty=positive(p.get("size"))
 side=str(p.get("side","")).upper()
 issues=[]
 if leverage is None:issues.append("LEVERAGE_UNKNOWN")
 if liq is None:issues.append("LIQUIDATION_PRICE_UNKNOWN")
 if qty is None:issues.append("POSITION_SIZE_UNKNOWN")
 if side not in ("LONG","SHORT"):issues.append("SIDE_UNKNOWN")
 if not p.get("marginType"):issues.append("MARGIN_MODE_UNKNOWN")
 return {"symbol":p.get("symbol"),"side":side,"leverage":str(leverage) if leverage else None,
         "liquidationPrice":str(liq) if liq else None,"issues":issues,
         "status":"READ_ONLY_REVIEW" if not issues else "INCOMPLETE"}
def audit():
 snapshot=json.loads((ROOT/"positions_readonly_latest.json").read_text(encoding="utf-8"))
 data={"asOf":datetime.now(timezone.utc).isoformat(),"sourceObservedAt":snapshot["observedAt"],
       "tradingEnabled":False,"items":[review(p) for p in snapshot["positions"]]}
 tmp=ROOT/"risk_review.tmp";tmp.write_text(json.dumps(data,indent=2),encoding="utf-8")
 tmp.replace(ROOT/"risk_review_latest.json")
 return data
if __name__=="__main__":
 for item in audit()["items"]:print(item["symbol"],item["status"],"issues",item["issues"])
