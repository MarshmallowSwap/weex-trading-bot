"""LIVE pilot controller dry-run. Persistent reservation precedes simulated submit.
No SDK write methods available. Does not affect manual positions.
"""
import json
from pathlib import Path
from live_sdk_intent_journal import reserve,mark_unknown
ROOT=Path(__file__).resolve().parent
def process(signal_id, symbol="ETHUSDT",*,db_path=None):
 prod=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
 pilot=json.loads((ROOT/"weex_live_1x_pilot_config.json").read_text(encoding="utf-8"))
 if prod["execution"]["enabled"] or pilot["executionEnabled"] or pilot["liveOrderSubmissionAllowed"]:
  return {"sent":False,"reason":"EXECUTION_CONFIG_NOT_SAFE"}
 if symbol!="ETHUSDT":return {"sent":False,"reason":"NOT_PILOT_SYMBOL"}
 reservation=reserve(signal_id,symbol,db_path=db_path)
 if reservation.get("reason")=="EXISTING_RESERVATION":
  return {"sent":False,"reason":"ALREADY_RESERVED_DO_NOT_RESUBMIT","clientOrderId":reservation["clientOrderId"]}
 mark_unknown(signal_id,db_path)
 return {"sent":False,"reason":"DRY_RUN_SUBMISSION_UNKNOWN","clientOrderId":reservation["clientOrderId"],
         "mustReconcileBeforeRetry":True}
