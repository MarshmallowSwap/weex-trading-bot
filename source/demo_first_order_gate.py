"""Strict gate before the FIRST demo order. Never sends orders."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
def assess(*,balance_ok,positions_ok,history_ok,exit_procedure_verified,client_binding_ready,request_demo_only):
 blockers=[]
 for ok,name in ((balance_ok,"DEMO_BALANCE"),(positions_ok,"DEMO_POSITIONS"),(history_ok,"DEMO_HISTORY"),(exit_procedure_verified,"SAFE_DEMO_EXIT"),(client_binding_ready,"CLIENT_ID_BINDING"),(request_demo_only,"DEMO_ISOLATION")):
  if not ok:blockers.append(name)
 return {"orderAuthorized":not blockers,"blockedBy":blockers,"ordersSubmitted":False}
if __name__=="__main__":
 d=json.loads((ROOT/"demo_execution_preflight_latest.json").read_text(encoding="utf-8"))
 r=assess(balance_ok=d["sources"]["balance"]["ok"],positions_ok=d["sources"]["positions"]["ok"],history_ok=d["sources"]["history"]["ok"],exit_procedure_verified=False,client_binding_ready=False,request_demo_only=True)
 (ROOT/"demo_first_order_gate_latest.json").write_text(json.dumps(r,indent=2),encoding="utf-8")
 print("DEMO_FIRST_ORDER", "GO" if r["orderAuthorized"] else "NO_GO", "blockers",r["blockedBy"])
