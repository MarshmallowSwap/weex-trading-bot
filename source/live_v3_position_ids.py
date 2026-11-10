"""WEEX V3 read-only position identity: exchange returns id, close route expects positionId."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
R=Path(__file__).resolve().parent
rows=query("/capi/v3/account/position/allPosition")
if not isinstance(rows,list):raise ValueError("Unexpected schema")
report={"checkedAt":datetime.now(timezone.utc).isoformat(),"positions":[],"ordersSubmitted":False}
for p in rows:
 pid=p.get("id")
 report["positions"].append({"symbol":p.get("symbol"),"side":p.get("side"),
 "hasExchangePositionId":bool(pid and str(pid).isdigit()),
 "closeParameterName":"positionId",
 "manualOrUnverified":True,"automaticCloseAllowed":False})
(R/"live_v3_position_ids_latest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("positions",len(rows),"with V3 id",sum(x["hasExchangePositionId"] for x in report["positions"]))
for x in report["positions"]:print(x["symbol"],x["side"],"id_present",x["hasExchangePositionId"],"autoclose",False)
