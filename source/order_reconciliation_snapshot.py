"""Read-only reconciliation snapshot from open and historical WEEX orders."""
import json
from datetime import datetime,timezone
from pathlib import Path
from order_reconciliation_readonly import fetch
ROOT=Path(__file__).resolve().parent
def capture():
 raw=fetch()
 overview={}
 complete=True
 for endpoint,value in raw.items():
  if value["status"]!="OK":complete=False
  overview[endpoint]={"status":value["status"],"count":value.get("count",0)}
 result={"checkedAt":datetime.now(timezone.utc).isoformat(),
         "allEndpointsOk":complete,"sources":overview,
         "activeOrderCount":raw.get("/capi/v3/openOrders?limit=100&page=0",{}).get("count"),
         "reconciliationCertified":False,
         "limitations":["Open orders result only one page","History result only one page","No bot intent to WEEX clientOrderId binding","No live order writes"]}
 target=ROOT/"order_reconciliation_status_latest.json"
 tmp=target.with_suffix(".tmp")
 tmp.write_text(json.dumps(result,indent=2),encoding="utf-8")
 tmp.replace(target)
 return result
if __name__=="__main__":
 s=capture()
 print("sources_healthy",s["allEndpointsOk"],"open",s["activeOrderCount"],"certified",s["reconciliationCertified"])
