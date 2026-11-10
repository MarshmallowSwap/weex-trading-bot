"""Read-only attribution evidence based on before/after exchange positions and confirmed order fills.
Never authorizes trading or closes positions; manual contamination fails closed.
"""
from decimal import Decimal,InvalidOperation
def amount(v):
 try:
  n=Decimal(str(v))
  return n if n.is_finite() and n>=0 else None
 except (InvalidOperation,TypeError,ValueError):return None
def evaluate(before,after,order,*,before_complete,after_complete,exclusive_bot_window):
 if not(before_complete and after_complete and exclusive_bot_window):
  return {"verified":False,"reason":"INCOMPLETE_OR_CONTAMINATED_WINDOW"}
 if not isinstance(before,list) or not isinstance(after,list) or not isinstance(order,dict):
  return {"verified":False,"reason":"INVALID_EVIDENCE"}
 if order.get("verified") is not True or not order.get("clientOrderId") or not order.get("orderId"):
  return {"verified":False,"reason":"UNVERIFIED_BOT_ORDER"}
 sym=order.get("symbol");side=order.get("positionSide")
 if side not in ("LONG","SHORT") or not sym:return {"verified":False,"reason":"INVALID_ORDER_SIDE"}
 prior=[p for p in before if p.get("symbol")==sym and p.get("side")==side]
 later=[p for p in after if p.get("symbol")==sym and p.get("side")==side]
 if prior or len(later)!=1:return {"verified":False,"reason":"PREEXISTING_OR_AMBIGUOUS_POSITION"}
 pos=later[0]; size=amount(pos.get("size"));filled=amount(order.get("executedQty"))
 if size is None or filled is None or size==0 or filled==0 or size!=filled:
  return {"verified":False,"reason":"SIZE_MISMATCH"}
 if not str(pos.get("id","")).isdigit():return {"verified":False,"reason":"NO_POSITION_ID"}
 return {"verified":False,"reason":"EXCHANGE_SIDE_OWNERSHIP_NOT_PROVEN","candidateId":str(pos["id"]),"closingAllowed":False}
