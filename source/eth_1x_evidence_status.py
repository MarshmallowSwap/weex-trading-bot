"""Independent evidence status for ETHUSDT pilot, no exchange writes.
A field absent from a report is UNKNOWN, not PASS.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
def load(n):
 try:return json.loads((R/n).read_text(encoding="utf-8"))
 except (OSError,ValueError):return {}
def recent(obj,key,mins):
 try:
  age=(datetime.now(timezone.utc)-datetime.fromisoformat(obj[key].replace("Z","+00:00"))).total_seconds()
  return 0<=age<=mins*60
 except (KeyError,ValueError,TypeError,AttributeError):return False
def run():
 runner=load("eth_1x_release_runner_latest.json")
 snap=load("eth_1x_release_snapshot.json")
 recon=load("weex_e2e_reconciliation_latest.json")
 evidence={
 "account_pilot_fresh":{"status":"PASS" if recent(runner,"checkedAt",10) else "STALE","source":"eth_1x_release_runner_latest.json"},
 "reference_price_fresh":{"status":"PASS" if recent(snap,"asOf",10) else "STALE","source":"eth_1x_release_snapshot.json"},
 "order_history_fresh":{"status":"PASS" if recent(recon,"checkedAt",10) else "STALE","source":"weex_e2e_reconciliation_latest.json"},
 "real_bot_order_binding":{"status":"NOT_PROVEN","source":"no bot-bound real order evidence"},
 "exchange_close_by_position_id":{"status":"NOT_PROVEN","source":"no bot-owned position close execution evidence"},
 "restart_after_real_exchange_fill":{"status":"NOT_PROVEN","source":"offline tests only"},
 "5usdt_exchange_order_acceptance":{"status":"NOT_PROVEN","source":"indicative notional only"}
 }
 result={"checkedAt":datetime.now(timezone.utc).isoformat(),"pilotDecision":"NO_GO",
 "evidence":evidence,"exchangeWrites":False,"manualPositionsModified":False}
 target=R/"eth_1x_evidence_status_latest.json";target.write_text(json.dumps(result,indent=2),encoding="utf-8")
 print("EVIDENCE",[(k,v["status"]) for k,v in evidence.items()])
 return result
if __name__=="__main__":run()
