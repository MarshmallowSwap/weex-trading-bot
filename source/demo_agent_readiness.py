"""Demo readiness inventory: no order submission."""
import json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from weex_demo_firewall import DEMO_SYMBOLS
ROOT=Path(__file__).resolve().parent
testfiles=("test_weex_demo_firewall_v2.py","test_weex_agent_orchestrator.py","test_position_ownership_gate.py",
"test_max_cross_leverage_resolver.py","test_position_manager_integrated.py",
"test_protection_coverage_v2.py","test_residual_protection_reconcile.py","test_crash_recovery_readonly.py")
results=[]
for n in testfiles:
 p=subprocess.run([sys.executable,str(ROOT/n)],cwd=ROOT,capture_output=True,text=True,timeout=30)
 results.append({"suite":n,"passed":p.returncode==0,"tail":(p.stdout+p.stderr)[-160:]})
report={"at":datetime.now(timezone.utc).isoformat(),"environment":"DEMO_READ_AND_OFFLINE_TEST",
 "documentedExampleSymbols":sorted(DEMO_SYMBOLS),"verifiedCompleteDemoUniverse":False,
 "testSuites":results,"passed":sum(x["passed"] for x in results),"total":len(results),
 "demoOrdersSubmitted":0,"realOrdersSubmitted":0,
 "next":"Discover complete demo symbol availability via exchange-authoritative method; then conduct bounded demo execution tests"}
p=ROOT/"demo_agent_readiness_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(report,indent=2),encoding="utf-8");t.replace(p)
print("SUITES",report["passed"],"/",report["total"],"DEMO_SYMBOLS_KNOWN",report["documentedExampleSymbols"],"ORDERS",0)
for x in results:
 if not x["passed"]:print("FAIL",x["suite"],x["tail"])
