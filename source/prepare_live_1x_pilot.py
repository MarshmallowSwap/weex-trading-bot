"""Isolated 1x live pilot configuration; preparation only, no exchange writes."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
main=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
assert main["execution"]["enabled"] is False
config={
 "createdAt":datetime.now(timezone.utc).isoformat(),
 "environment":"LIVE_PILOT_PREPARATION",
 "exchange":"WEEX",
 "leverage":1,
 "marginMode":"CROSS",
 "initialMarginTargetUSDT":"5",
 "maxNewOrders":1,
 "maxAdditionalNotionalUSDT":"5",
 "manualPositionsProtected":True,
 "requireNoExistingPositionOnSymbol":True,
 "requireVerifiedCloseOnly":True,
 "requireVerifiedOrderLifecycle":True,
 "requireExplicitTestOrderApproval":True,
 "executionEnabled":False,
 "liveOrderSubmissionAllowed":False,
 "warning":"1x Cross still risks actual USDT and shared wallet collateral"
}
target=ROOT/"weex_live_1x_pilot_config.json"
target.write_text(json.dumps(config,indent=2),encoding="utf-8")
print("PILOT PREPARED", "1x CROSS", "ORDERS_DISABLED",not config["executionEnabled"],"PRODUCTION_UNCHANGED",not main["execution"]["enabled"])
