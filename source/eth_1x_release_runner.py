"""ETHUSDT 1x release runner: one read-only execution path, no exchange writes.
Collect actual account state, run production-related tests, output blockers.
"""
import json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
suites=["test_live_1x_order_gate.py","test_live_1x_close_plan.py",
 "test_live_1x_position_binding.py","test_live_1x_close_guard.py",
 "test_live_pilot_history_gate.py","test_position_ownership_gate.py"]
def run():
 cfg=json.loads((ROOT/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))
 main=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
 positions=query("/capi/v3/account/position/allPosition")
 open_orders=query("/capi/v3/openOrders?limit=100&page=0")
 mode=query("/capi/v3/account/symbolConfig?symbol=ETHUSDT")
 if isinstance(mode,list):mode=next((r for r in mode if r.get("symbol")=="ETHUSDT"),{})
 if not isinstance(positions,list) or not isinstance(open_orders,list) or not isinstance(mode,dict):
  raise ValueError("WEEX account snapshot not available")
 testresults=[]
 for name in suites:
  p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,capture_output=True,text=True,timeout=20)
  testresults.append({"suite":name,"passed":p.returncode==0,"tail":(p.stdout+p.stderr)[-180:]})
 checks={
  "ETHUSDT_without_positions_or_orders":not any(p.get("symbol")=="ETHUSDT" for p in positions+open_orders),
  "account_cross_1x":mode.get("marginType") in ("CROSS","CROSSED") and str(mode.get("crossLeverage"))=="1",
  "live_execution_disabled":main.get("execution",{}).get("enabled") is False and cfg.get("executionEnabled") is False,
  "all_local_suites_pass":all(t["passed"] for t in testresults),
  "5_USDT_order_exchange_accepted":False,
  "client_order_id_exchange_bound":False,
  "close_by_position_id_exchange_verified":False,
  "restart_reconciliation_verified_with_real_bot_order":False
 }
 out={"checkedAt":datetime.now(timezone.utc).isoformat(),"environment":"LIVE_READ_ONLY",
      "symbol":"ETHUSDT","checks":checks,"tests":testresults,"passed":sum(checks.values()),
      "total":len(checks),"decision":"NO_GO","realOrdersPlaced":False,
      "manualPositionsPreserved":True,"nextAction":"Validate order execution and close lifecycle in a guarded pilot before enabling autonomous orders"}
 dest=ROOT/"eth_1x_release_runner_latest.json";tmp=dest.with_suffix(".tmp")
 tmp.write_text(json.dumps(out,indent=2),encoding="utf-8");tmp.replace(dest)
 return out
if __name__=="__main__":
 o=run();print("ETH 1X",o["decision"],o["passed"],"/",o["total"],"LOCAL_TEST_SUITES",sum(x["passed"] for x in o["tests"]),"/",len(o["tests"]))
 for k,v in o["checks"].items():print("PASS" if v else "BLOCK",k)
