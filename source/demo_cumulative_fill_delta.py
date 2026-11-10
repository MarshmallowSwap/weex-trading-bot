"""Read-only cumulative-fill delta calculation, never infers entry/exit order role."""
from decimal import Decimal,InvalidOperation
def amount(x):
 try:
  q=Decimal(str(x))
  return q if q.is_finite() and q>=0 else None
 except (ValueError,InvalidOperation,TypeError):return None
def delta(previous,observation):
 if not observation.get("verified") or not observation.get("orderId"):
  return {"accepted":False,"reason":"UNVERIFIED_EXCHANGE_OBSERVATION"}
 total=amount(observation.get("total"));filled=amount(observation.get("filled"))
 if total is None or total<=0 or filled is None or filled>total:
  return {"accepted":False,"reason":"INVALID_CUMULATIVE_FILL"}
 old=amount(previous.get("filled","0")) if previous else Decimal(0)
 if old is None or filled<old:
  return {"accepted":False,"reason":"CUMULATIVE_FILL_REGRESSION"}
 if previous and previous.get("orderId")!=observation["orderId"]:
  return {"accepted":False,"reason":"ORDER_ID_CHANGED"}
 increase=filled-old
 return {"accepted":True,"delta":str(increase),"changed":increase>0,
         "newCumulative":str(filled),"roleVerified":False,"applyPosition":False,
         "reason":"Order role and exchange execution identity not certified"}
