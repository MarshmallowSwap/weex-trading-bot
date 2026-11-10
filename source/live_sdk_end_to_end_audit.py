"""WEEX LIVE: fail-closed end-to-end order observation, never sends orders."""
from live_sdk_reservation_reconcile import inspect
from live_sdk_fill_observer import reconcile_fills
def evaluate(history,opened,trades,db_path):
 reservations=inspect(history,opened,db_path=db_path)
 if not reservations.get("safe"):
  return {"state":"BLOCKED","reason":"RESERVATION_AMBIGUOUS","ordersSent":False,"canSubmit":False,"canClose":False}
 items=reservations["items"]
 if not items:
  return {"state":"NO_BOT_ORDER_EVIDENCE","reservations":0,"unresolved":0,"fillMismatches":0,
          "canSubmit":False,"canClose":False,"ordersSent":False}
 fills=reconcile_fills(history+opened,trades,items)
 if not fills.get("valid"):
  return {"state":"BLOCKED","reason":"FILL_OBSERVATIONS_INVALID","ordersSent":False,"canSubmit":False,"canClose":False}
 blockers=[x for x in fills.get("observations",[]) if x["state"]!="OBSERVED_MATCH"]
 unresolved=[r for r in items if r["reconciliation"]!="EXCHANGE_ORDER_OBSERVED"]
 return {"state":"READ_ONLY_MATCHED" if not blockers and not unresolved else "RECONCILIATION_REQUIRED",
  "reservations":len(items),"unresolved":len(unresolved),"fillMismatches":len(blockers),
  "canSubmit":False,"canClose":False,"ordersSent":False}
