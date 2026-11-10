"""Fail-closed quantitative TP/SL coverage check using verified protection quantity."""
from decimal import Decimal,InvalidOperation
def check(position,orders,pagination_complete=False):
 if not pagination_complete:return {"covered":False,"reason":"PAGINATION_INCOMPLETE"}
 try:
  size=Decimal(str(position["size"]))
  if not size.is_finite() or size<=0:raise ValueError()
 except (KeyError,ValueError,InvalidOperation,TypeError):return {"covered":False,"reason":"INVALID_POSITION_SIZE"}
 symbol=position.get("symbol");side=str(position.get("side","")).upper()
 if side not in ("LONG","SHORT"):return {"covered":False,"reason":"INVALID_SIDE"}
 matching=[x for x in orders if x.get("symbol")==symbol and str(x.get("positionSide","")).upper()==side]
 if not matching:return {"covered":False,"reason":"NO_MATCHING_PROTECTION"}
 total=Decimal(0)
 for order in matching:
  if str(order.get("status",order.get("algoStatus",""))).upper() not in ("NEW","OPEN","ACTIVE","UNACTIVATED"):
   continue
  if order.get("reduceOnly") is not True:return {"covered":False,"reason":"REDUCE_ONLY_UNVERIFIED"}
  if order.get("quantityUnitVerified") is not True:return {"covered":False,"reason":"QUANTITY_UNITS_UNVERIFIED"}
  try:
   qty=Decimal(str(order["quantity"]))
   if not qty.is_finite() or qty<=0:raise ValueError()
  except (KeyError,ValueError,InvalidOperation,TypeError):return {"covered":False,"reason":"INVALID_PROTECTIVE_QUANTITY"}
  total+=qty
 if total<size:return {"covered":False,"reason":"INSUFFICIENT_COVERAGE","coveredQty":str(total)}
 return {"covered":True,"reason":"COVERAGE_CHECK_ONLY","coveredQty":str(total),"canSubmitOrders":False}
