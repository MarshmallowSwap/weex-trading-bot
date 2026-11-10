"""Read-only 1x WEEX pilot candidate inventory; no order or leverage changes."""
import json
from pathlib import Path
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone
from monitor import query
R=Path(__file__).resolve().parent
positions=query("/capi/v3/account/position/allPosition")
orders=query("/capi/v3/openOrders?limit=100&page=0")
universe=json.loads((R/"universe_latest.json").read_text(encoding="utf-8"))
if not isinstance(positions,list) or not isinstance(orders,list):raise RuntimeError("ACCOUNT_SNAPSHOT_FAILED")
blocked={str(x.get("symbol")) for x in positions+orders if x.get("symbol")}
selected=[x["symbol"] for x in universe["symbols"] if x.get("symbol") and x["symbol"] not in blocked][:12]
rows=[]
for symbol in selected:
 try:
  c=query("/capi/v3/account/symbolConfig?symbol="+symbol)
  if isinstance(c,list):c=next((x for x in c if x.get("symbol")==symbol),{})
  rows.append({"symbol":symbol,"accountMode":c.get("marginType"),"crossLeverage":c.get("crossLeverage"),"configReadable":bool(c)})
 except Exception as e:rows.append({"symbol":symbol,"error":type(e).__name__})
report={"at":datetime.now(timezone.utc).isoformat(),"manualOrBusySymbols":sorted(blocked),"accountPositions":len(positions),"openOrders":len(orders),
 "pilotCandidates":rows,"minNotionalCertified":False,"exitExecutionCertified":False,"canTradePilot":False,"ordersSubmitted":False}
(R/"live_1x_candidates_latest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("positions",len(positions),"open",len(orders),"candidates",len(rows),"modes",[(x["symbol"],x.get("crossLeverage")) for x in rows[:5]],"writes",False)
