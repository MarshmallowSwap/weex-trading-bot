"""Single WEEX LIVE pilot cycle: SDK observations + order intent + TP readiness.
Read-only by default: no exchange submit/close; manual holdings excluded.
"""
from decimal import Decimal,InvalidOperation
def inspect_cycle(signal,account,orders,trades,*,tp_plan=None):
 if signal.get("symbol")!="ETHUSDT" or signal.get("decision") not in ("LONG","SHORT"):
  return {"stage":"WAIT","reason":"NO_VALID_SIGNAL","submitted":False}
 if any(x.get("symbol")=="ETHUSDT" for x in account):
  return {"stage":"BLOCKED","reason":"EXISTING_POSITION","submitted":False}
 if not signal.get("verifiedBotClientOrderId"):
  return {"stage":"PREPARE_INTENT","reason":"BOT_ORDER_NOT_SUBMITTED","submitted":False}
 client=signal["verifiedBotClientOrderId"]
 matches=[x for x in orders if x.get("clientOrderId")==client]
 if len(matches)!=1 or not matches[0].get("orderId"):
  return {"stage":"RECONCILIATION_REQUIRED","reason":"MISSING_OR_DUPLICATE_ORDER","submitted":False}
 o=matches[0];fills=[x for x in trades if str(x.get("orderId"))==str(o["orderId"])]
 try:
  total=sum((Decimal(str(t["qty"])) for t in fills),Decimal(0))
  expected=Decimal(str(o["executedQty"]))
  if not total.is_finite() or total<=0 or total!=expected:raise ValueError()
 except (ValueError,InvalidOperation,TypeError,KeyError):
  return {"stage":"RECONCILIATION_REQUIRED","reason":"FILL_MISMATCH","submitted":False}
 if not tp_plan or tp_plan.get("orderSubmissionEnabled") is not False:
  return {"stage":"TP_PLANNING_REQUIRED","reason":"TP_NOT_VERIFIED","submitted":False}
 return {"stage":"TP_PREVIEW_READY","clientOrderId":client,"filledQty":str(total),
         "tpPrice":tp_plan.get("takeProfitPrice"),"tpSubmitted":False,"submitted":False}
