"""Read-only protection gap report. Never infers certified protection from unknown units."""
import json
from datetime import datetime,timezone
from pathlib import Path
from monitor import query
from protection_pagination import all_protections
from protection_coverage_v2 import coverage
from protection_policy import classify
ROOT=Path(__file__).resolve().parent
def run():
 cfg=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
 positions=query("/capi/v3/account/position/allPosition")
 if not isinstance(positions,list):raise ValueError("Invalid position response")
 books=all_protections()
 allcomplete=books["allComplete"]
 reports=[]
 for p in positions:
  result=coverage(p,books["conditional"]["records"],books["trailing"]["records"],allcomplete)
  reports.append({"symbol":p.get("symbol"),"side":p.get("side"),"coverage":result,
    "stopLossRequested":bool(cfg["risk"]["stopLoss"].get("enabled",False)),
    "classification":classify(result,bool(cfg["risk"]["stopLoss"].get("enabled",False))),
    "action":"OBSERVE_ONLY"})
 report={"checkedAt":datetime.now(timezone.utc).isoformat(),"positions":len(positions),
  "conditional":len(books["conditional"]["records"]),"trailing":len(books["trailing"]["records"]),
  "paginationCompleteWithinBounds":allcomplete,"coverage":reports,"exchangeOrdersModified":False,
  "warning":"With SL OFF a position can liquidate. Quantities and reduce-only are not yet certified."}
 dest=ROOT/"protection_gap_report_latest.json";tmp=dest.with_suffix(".tmp")
 tmp.write_text(json.dumps(report,indent=2),encoding="utf-8");tmp.replace(dest)
 return report
if __name__=="__main__":
 r=run();print("positions",r["positions"],"conditional",r["conditional"],"trailing",r["trailing"],"modified",r["exchangeOrdersModified"])
