"""WEEX demo GET inventory, authenticated read-only; no production mutations."""
from monitor import query
from datetime import datetime,timezone
import json
from pathlib import Path
root=Path(__file__).resolve().parent
sources={"history":"/capi/v3/sim/order/history?symbol=BTCSUSDT&limit=100&page=0","positions":"/capi/v3/sim/position/allPosition","balance":"/capi/v3/sim/balance"}
summary={}
for name,path in sources.items():
 try:
  result=query(path)
  if not isinstance(result,list):raise ValueError("SCHEMA_NOT_LIST")
  summary[name]={"ok":True,"count":len(result)}
  if name=="history":summary[name]["matchingClientOrderIds"]=sum(bool(r.get("clientOrderId")) for r in result if isinstance(r,dict))
 except Exception as exc:summary[name]={"ok":False,"reason":type(exc).__name__}
report={"checkedAt":datetime.now(timezone.utc).isoformat(),"sources":summary,"demoTradesExecuted":False}
(root/"demo_execution_preflight_latest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report))
