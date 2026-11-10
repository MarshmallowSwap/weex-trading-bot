"""Minimal WEEX signal -> intent -> SDK order preview -> reconciliation -> TP plan.
No exchange writes. Does not alter demo, shadow or Telegram.
"""
from decimal import Decimal
from live_sdk_intent_journal import reserve
from live_sdk_end_to_end_audit import evaluate
from exit_order_planner import plan as plan_exit
def pipeline(signal,positions,open_orders,*,journal_path,history=None,trades=None,
             break_even=None,fee_rate=None,tick_size=None,profit_usdt="0.5"):
 if signal.get("decision") not in ("LONG","SHORT"):
  return {"stage":"WAIT","reason":"NO_SIGNAL","orderSubmitted":False}
 if signal.get("symbol")!="ETHUSDT":
  return {"stage":"BLOCKED","reason":"PILOT_SYMBOL_ONLY","orderSubmitted":False}
 if not isinstance(positions,list) or not isinstance(open_orders,list):
  return {"stage":"BLOCKED","reason":"INVALID_ACCOUNT_STATE","orderSubmitted":False}
 if any(x.get("symbol")=="ETHUSDT" for x in positions+open_orders):
  return {"stage":"BLOCKED","reason":"EXISTING_EXPOSURE","orderSubmitted":False}
 if signal.get("momentum",{}).get("confirmed") is not True or signal.get("realOrderBook",{}).get("passed") is not True:
  return {"stage":"WAIT","reason":"SIGNAL_NOT_FULLY_VALIDATED","orderSubmitted":False}
 # This is a candidate only: all real writes remain disabled.
 sid=str(signal.get("signalId") or "")
 if not sid:return {"stage":"BLOCKED","reason":"MISSING_SIGNAL_ID","orderSubmitted":False}
 reservation=reserve(sid,"ETHUSDT",journal_path)
 if reservation.get("reason")=="EXISTING_RESERVATION":
  return {"stage":"RECONCILIATION_REQUIRED","reason":"NO_RETRY","clientOrderId":reservation["clientOrderId"],"orderSubmitted":False}
 client=reservation["clientOrderId"]
 result={"stage":"INTENT_RESERVED","clientOrderId":client,
         "orderPreview":{"symbol":"ETHUSDT","positionSide":signal["decision"],
                         "newClientOrderId":client},
         "orderSubmitted":False,"tpSubmitted":False}
 if history is None or trades is None:return result
 result["reconciliation"]=evaluate(history,open_orders,trades,journal_path)
 # TP can be planned only against verified position quantity and break-even evidence.
 if all(v is not None for v in (break_even,fee_rate,tick_size)) and signal.get("verifiedFilledPosition") is True:
  result["tpPreview"]=plan_exit({"side":signal["decision"],"remainingBaseQty":signal["filledQty"]},
     break_even=break_even,profit_usdt=profit_usdt,fee_rate=fee_rate,tick_size=tick_size)
 return result
