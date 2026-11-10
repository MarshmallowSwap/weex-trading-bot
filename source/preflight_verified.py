"""Fail-closed WEEX preflight with timestamp and evidence integrity; no orders."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
def load(name):
 try:return json.loads((ROOT/name).read_text(encoding="utf-8"))
 except (OSError,ValueError,TypeError):return {}
def fresh(data,key,minutes):
 try:
  stamp=datetime.fromisoformat(data[key].replace("Z","+00:00"))
  seconds=(datetime.now(timezone.utc)-stamp).total_seconds()
  return 0<=seconds<=minutes*60
 except (KeyError,ValueError,TypeError,AttributeError):return False
def audit():
 cfg=load("weex_ai_risk_config.json")
 scan=load("universe_latest.json")
 agent=load("agent_health_latest.json")
 orders=load("weex_e2e_reconciliation_latest.json")
 positions=load("position_manager_integrated_latest.json")
 protected=load("position_protection_audit_latest.json")
 checks={
 "scanner_updated_26h":fresh(scan,"scannedAt",1560) and scan.get("count",0)>0,
 "agent_heartbeat_updated_30m":fresh(agent,"checkedAt",30) and agent.get("status")=="OK",
 "read_only_positions_updated_10m":fresh(positions,"asOf",10) and positions.get("exchangeWrites") is False,
 "order_snapshot_updated_10m":fresh(orders,"checkedAt",10) and orders.get("liveExecutionEnabled") is False,
 "conditional_snapshot_updated_10m":fresh(protected,"asOf",10) and protected.get("exchangeModifications") is False,
 "order_client_id_binding_live_proven":False,
 "account_leverage_tier_verified":False,
 "order_book_units_verified":False,
 "tp_exit_order_live_verified":False,
 "crash_recovery_with_exchange_order_verified":False,
 "trading_disabled_during_preflight":cfg.get("execution",{}).get("enabled") is False
 }
 state="GO" if all(checks.values()) else "NO_GO"
 result={"at":datetime.now(timezone.utc).isoformat(),"gate":state,"checks":checks,
         "passed":sum(checks.values()),"total":len(checks),"ordersSubmitted":False}
 target=ROOT/"live_release_gate_latest.json";tmp=target.with_suffix(".tmp")
 tmp.write_text(json.dumps(result,indent=2),encoding="utf-8");tmp.replace(target)
 return result
if __name__=="__main__":
 r=audit()
 print("RELEASE",r["gate"],r["passed"],"/",r["total"])
 for k,v in r["checks"].items():print("PASS" if v else "BLOCK",k)
