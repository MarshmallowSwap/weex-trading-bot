"""Conservative LIVE pilot ownership evidence. No account mutations."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
p=json.loads((ROOT/"live_position_identity_audit_latest.json").read_text(encoding="utf-8"))
cfg=json.loads((ROOT/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))
blockers=[]
if any(not x["hasPositionId"] for x in p["positions"]):blockers.append("POSITION_ID_ABSENT_IN_POSITION_SNAPSHOT")
if not cfg.get("requireVerifiedCloseOnly"):blockers.append("CLOSE_ONLY_REQUIRED")
blockers+=["BOT_OPEN_ORDER_TO_POSITION_PROVENANCE_NOT_CERTIFIED","EXCHANGE_CLOSE_NOT_TESTED"]
result={"checkedAt":datetime.now(timezone.utc).isoformat(),"livePilot":"NO_GO",
 "manualOrUnknownPositions":p["count"],"blockers":blockers,"ordersSent":0,
 "pilotConfigStillDisabled":not cfg["executionEnabled"]}
out=ROOT/"live_1x_ownership_gate_latest.json";out.write_text(json.dumps(result,indent=2),encoding="utf-8")
print("LIVE_PILOT",result["livePilot"],"BLOCKERS",len(blockers),"ORDERS",result["ordersSent"])
