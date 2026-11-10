"""Release decision bundle; read-only and fail-closed.
No orders, leverage changes, stop modifications or Telegram messages.
"""
import json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
tests=["test_position_ownership_gate.py","test_position_manager_integrated.py","test_max_cross_leverage_resolver.py","test_protection_coverage_v2.py","test_residual_protection_reconcile.py","test_protection_policy.py"]
results=[]
for name in tests:
 p=subprocess.run([sys.executable,str(ROOT/name)],cwd=str(ROOT),capture_output=True,text=True,timeout=30)
 results.append({"test":name,"passed":p.returncode==0,"summary":(p.stdout+" "+p.stderr)[-500:]})
from preflight_verified import audit
gate=audit()
risk=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
manual_positions_not_owned=True
decision={
 "checkedAt":datetime.now(timezone.utc).isoformat(),
 "decision":"GO" if gate["gate"]=="GO" and all(x["passed"] for x in results) else "NO_GO",
 "preflight":gate,"tests":results,
 "testsPassed":sum(x["passed"] for x in results),"testsTotal":len(results),
 "executionEnabled":risk["execution"]["enabled"],
 "marginMode":risk["risk"]["marginModePreference"],
 "leveragePreference":risk["risk"].get("leveragePreference"),
 "manualPositionPolicy":"UNBOUND_POSITIONS_READ_ONLY",
 "manualPositionsNotModified":manual_positions_not_owned,
 "auditSubmittedOrders":False,
 "pending":["real verified order client ID binding","account permitted maximum leverage via API","verified depth units","hedge CROSS TP execution verification","crash restart exchange recovery"],
 "decisionBasis":"No live activation while any critical gate remains unverified"
}
out=ROOT/"WEEX_LIVE_DECISION_REPORT.json";tmp=out.with_suffix(".tmp")
tmp.write_text(json.dumps(decision,indent=2,ensure_ascii=False),encoding="utf-8");tmp.replace(out)
print("DECISION",decision["decision"],"TEST_FILES",decision["testsPassed"],"/",decision["testsTotal"],"GATES",gate["passed"],"/",gate["total"],"EXECUTION",decision["executionEnabled"])
for t in results:
 print(("PASS" if t["passed"] else "FAIL"),t["test"])
