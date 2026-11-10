"""Read-only residual position / protection reconciliation.
Never modify WEEX orders. Fail closed if units or order states are unverified.
"""
from decimal import Decimal,InvalidOperation
def dec(value):
 try:
  n=Decimal(str(value))
  return n if n.is_finite() and n>=0 else None
 except (InvalidOperation,TypeError):return None
def check(position,protection,*,pagination_complete,units_verified=False):
 qty=dec(position.get("size"))
 if qty is None or not position.get("symbol"):return {"status":"UNKNOWN","reason":"INVALID_POSITION","canModify":False}
 if not pagination_complete:return {"status":"UNKNOWN","reason":"INCOMPLETE_PAGINATION","canModify":False}
 if not units_verified:return {"status":"UNKNOWN","reason":"UNVERIFIED_UNITS","canModify":False}
 protective=dec(protection.get("remainingQty"))
 if protective is None:return {"status":"UNKNOWN","reason":"INVALID_PROTECTION","canModify":False}
 if protective>qty:return {"status":"EXCESS_PROTECTION","excessQty":str(protective-qty),"canModify":False}
 if protective<qty:return {"status":"UNDER_PROTECTED","missingQty":str(qty-protective),"canModify":False}
 return {"status":"MATCHED","remainingQty":str(qty),"canModify":False}
