"""Inspect real demo history for reduceOnly and closing semantics. GET only."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
rows=query("/capi/v3/sim/order/history?symbol=BTCSUSDT&limit=100&page=0")
if not isinstance(rows,list):raise ValueError("INVALID_DEMO_HISTORY")
fields=sorted(set().union(*(set(o.keys()) for o in rows if isinstance(o,dict)))) if rows else []
flags=[{"clientOrderIdPresent":bool(o.get("clientOrderId")),
        "reduceOnlyValue":o.get("reduceOnly"),
        "positionSide":o.get("positionSide"),
        "side":o.get("side"),
        "status":o.get("status")} for o in rows if isinstance(o,dict)]
verified=any(x["reduceOnlyValue"] is True for x in flags)
result={"checkedAt":datetime.now(timezone.utc).isoformat(),
        "demoOrdersObserved":len(rows),
        "fieldsObserved":fields,
        "reduceOnlyTrueObserved":verified,
        "dedicatedDemoCloseEndpointVerified":False,
        "closeOnlyBehaviorCertified":False,
        "noOrdersSubmitted":True,
        "nextAction":"Get provider confirmation of demo close-only semantics or a documented close route; do not infer from ordinary live API."}
out=ROOT/"demo_close_api_research_latest.json"
out.write_text(json.dumps(result,indent=2),encoding="utf-8")
print("Demo observed orders",len(rows),"reduceOnlyTrueObserved",verified,"closeOnlyCertified",False)
