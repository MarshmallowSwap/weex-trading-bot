"""WEEX position manager integration: fail-closed reconciliation in read-only mode."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from protection_pagination import all_protections
from protection_coverage_v2 import coverage
from protection_policy import classify
from position_ownership_gate import authorize
ROOT=Path(__file__).resolve().parent
def run():
 cfg=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
 from weex_account_observation import observe
 snapshot=observe(ROOT,max_age=5)
 pos=snapshot['positions']
 books={'conditional':{'records':snapshot['conditionalOrders']},'trailing':{'records':snapshot['trailingOrders']},'allComplete':True}
 complete=books["allComplete"]
 result=[]
 sl_required=bool(cfg["risk"]["stopLoss"]["enabled"])
 for p in pos:
  check=coverage(p,books["conditional"]["records"],books["trailing"]["records"],complete)
  policy=classify(check,sl_required)
  result.append({"symbol":p.get("symbol"),"side":p.get("side"),"coverage":check,
                 "policy":policy,"ownership":authorize("CLOSE",p,[],reconciled=False),
                 "quantitiesCertified":check.get("verified") is True,"modificationAllowed":False})
 coverage_certified=complete and all(
  x["coverage"].get("verified") is True and (x["coverage"].get("tpCovered") is True or x["coverage"].get("trailingCovered") is True)
  and (not sl_required or x["coverage"].get("slCovered") is True) for x in result)
 payload={"asOf":snapshot["observedAt"],"checkedAt":datetime.now(timezone.utc).isoformat(),"positions":len(pos),
   "conditionalOrders":len(books["conditional"]["records"]),"trailingOrders":len(books["trailing"]["records"]),
   "completeWithinBounds":complete,"items":result,"coverageCertified":coverage_certified,
   "exchangeWrites":False,"productionGate":"TP_COVERAGE_CERTIFIED_READ_ONLY" if coverage_certified else "NO_GO"}
 out=ROOT/"position_manager_integrated_latest.json";tmp=out.with_suffix(".tmp")
 tmp.write_text(json.dumps(payload,indent=2),encoding="utf-8");tmp.replace(out)
 return payload
if __name__=="__main__":
 p=run();print("positions",p["positions"],"conditional",p["conditionalOrders"],"trailing",p["trailingOrders"],"gate",p["productionGate"])
