"""Flag leverage tier disagreements; no account-leverage claims or trades."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/"weex_risk_tiers_5usdt_latest.json").read_text(encoding="utf-8"))
mismatches=[x for x in data["results"] if not x["publicTierSupportsAdvertised"]]
result={"at":datetime.now(timezone.utc).isoformat(),"status":"PUBLIC_BRACKETS_CHECKED",
"symbolsEvaluated":len(data["results"]),"advertisedLeverageTierMismatch":len(mismatches),
"mismatches":mismatches,"accountSpecificLeverageVerified":False,"ordersAllowed":False,
"nextVerification":"Confirm exact per-account leverage and order notional before approval"}
out=ROOT/"leverage_gate_evidence_latest.json"
out.write_text(json.dumps(result,indent=2),encoding="utf-8")
print("mismatches",len(mismatches),"account_leverage_certified",result["accountSpecificLeverageVerified"],"orders",result["ordersAllowed"])
