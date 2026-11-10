"""WEEX demo exit capability matrix from public API specification.
No order is submitted, and live closePositions must never be used for demo.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent
report={
 "checkedAt":datetime.now(timezone.utc).isoformat(),
 "documentedDemoEndpoints":{
  "placeOrder":{"method":"POST","path":"/capi/v3/sim/order"},
  "positions":{"method":"GET","path":"/capi/v3/sim/position/allPosition"},
  "history":{"method":"GET","path":"/capi/v3/sim/order/history"},
  "balance":{"method":"GET","path":"/capi/v3/sim/balance"}
 },
 "dedicatedDemoCloseDocumented":False,
 "dedicatedDemoCancelDocumented":False,
 "oppositeSideMarketOrderCertifiedReduceOnly":False,
 "productionCloseEndpointMustNotBeUsed":"/capi/v3/closePositions",
 "firstOrderExitReady":False,
 "ordersSent":False,
 "requiredEvidence":"WEEX confirmation or demo-specific execution showing a close-only order cannot increase/reverse exposure"
}
p=root/"demo_exit_capability_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(report,indent=2),encoding="utf-8");t.replace(p)
print("DEMO_EXIT", "NO_GO", "demo_close_documented",report["dedicatedDemoCloseDocumented"],"orders_sent",report["ordersSent"])
