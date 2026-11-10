"""Detect WEEX account mode mismatches before live execution. Read-only."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
observed=json.loads((ROOT/"symbol_config_readonly_latest.json").read_text(encoding="utf-8"))
target=cfg["risk"]["marginModePreference"].upper()
results=[]
for s in observed["accountSample"]:
 if s["status"]!="OK":
  results.append({"symbol":s["symbol"],"status":"UNKNOWN"});continue
 mismatch=(str(s["marginType"]).upper() not in ({"CROSS","CROSSED"} if target in ("CROSS","CROSSED") else {target}))
 results.append({"symbol":s["symbol"],"configuredMode":s["marginType"],
 "expectedMode":target,"modeMismatch":mismatch,"requiresChangeBeforeAutoTrading":mismatch})
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"sampleCount":len(results),
 "mismatches":sum(r.get("modeMismatch",False) for r in results),"findings":results,
 "accountMaximumLeverageVerified":False,"liveTradingEnabled":False}
f=ROOT/"margin_mode_mismatch_latest.json";f.write_text(json.dumps(out,indent=2),encoding="utf-8")
print("checked",out["sampleCount"],"margin_mismatch",out["mismatches"],"account_max_verified",out["accountMaximumLeverageVerified"])
