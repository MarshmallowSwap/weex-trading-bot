"""Read-only WEEX position identity inventory; exclude manual positions, never close them."""
import json
from datetime import datetime,timezone
from pathlib import Path
from monitor import query
ROOT=Path(__file__).resolve().parent
rows=query("/capi/v3/account/position/allPosition")
if not isinstance(rows,list):raise ValueError("Unexpected schema")
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"count":len(rows),"positions":[],"ordersSubmitted":False}
for p in rows:
 out["positions"].append({"symbol":p.get("symbol"),"side":p.get("side"),
  "hasPositionId":bool(p.get("positionId")),
  "hasOrderClientBinding":bool(p.get("clientOrderId")),
  "fields":sorted(p.keys()),"ownership":"UNVERIFIED_MANUAL_OR_MIXED",
  "automaticCloseAllowed":False})
f=ROOT/"live_position_identity_audit_latest.json"
f.write_text(json.dumps(out,indent=2),encoding="utf-8")
print("positions",len(rows))
for p in out["positions"]:print("symbol",p["symbol"],"side",p["side"],"positionId",p["hasPositionId"],"clientBinding",p["hasOrderClientBinding"])
