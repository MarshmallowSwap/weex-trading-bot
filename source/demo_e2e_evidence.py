"""WEEX demo end-to-end evidence gate: no synthetic flag can authorize first order.
Pure local inspection, no network writes.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
def read(name):
 try:return json.loads((ROOT/name).read_text(encoding="utf-8"))
 except (OSError,ValueError):return {}
def evaluate(health,recon,exit_evidence):
 checks={
  "demo_balance_accessible":health.get("balance",{}).get("accessible") is True,
  "demo_positions_accessible":health.get("positions",{}).get("accessible") is True,
  "client_binding_exchange_proven":recon.get("certified") is True and len(recon.get("intents",[]))>0,
  "demo_close_verified":exit_evidence.get("exchangeVerified") is True and exit_evidence.get("closeEndpoint",{}).get("dedicatedDemo") is True,
  "no_real_endpoint_used":exit_evidence.get("realEndpointsUsed") is False
 }
 # Synthetically supplied evidence must never be treated as operational certification.
 return {"ready":False,"checks":checks,"reason":"FIRST_ORDER_REQUIRES_INDEPENDENT_DEMO_EXIT_CERTIFICATION","ordersSent":False}
def run():
 result=evaluate(read("demo_health_latest.json"),read("demo_intent_reconciliation_latest.json"),read("demo_exit_exchange_evidence_latest.json"))
 result["checkedAt"]=datetime.now(timezone.utc).isoformat()
 p=ROOT/"demo_e2e_evidence_latest.json";t=p.with_suffix(".tmp")
 t.write_text(json.dumps(result,indent=2),encoding="utf-8");t.replace(p)
 return result
if __name__=="__main__":
 x=run();print("DEMO_E2E","NO_GO","checks",sum(x["checks"].values()),"/",len(x["checks"]),"orders",x["ordersSent"])
