"""WEEX protection auditor; fail-closed by TP/SL class, without double-counting."""
from decimal import Decimal,InvalidOperation

def decimal(value):
 try:
  v=Decimal(str(value))
  return v if v.is_finite() and v>0 else None
 except (InvalidOperation,TypeError):return None

def coverage(position,algos,trailing,complete):
 if not complete:return {"verified":False,"reason":"INCOMPLETE_PAGINATION"}
 symbol=position.get("symbol");side=str(position.get("side","")).upper()
 qty=decimal(position.get("size"))
 if not symbol or side not in ("LONG","SHORT") or qty is None:return {"verified":False,"reason":"INVALID_POSITION"}
 close_side="SELL" if side=="LONG" else "BUY"
 grouped={"TAKE_PROFIT":[],"STOP_LOSS":[],"TRAILING":[]}
 from weex_trailing import merge
 try:orders=merge(algos,trailing)
 except (ValueError,TypeError,ArithmeticError,KeyError):return {'verified':False,'reason':'TRAILING_SCHEMA_INVALID'}
 for o in orders:
  if o.get("symbol")!=symbol or str(o.get("positionSide","")).upper()!=side:continue
  typ=str(o.get("orderType",o.get("type",""))).upper()
  if "TRAILING" in typ:kind="TRAILING"
  elif "TAKE_PROFIT" in typ:kind="TAKE_PROFIT"
  elif "STOP" in typ or "LOSS" in typ:kind="STOP_LOSS"
  else:continue
  status=str(o.get("algoStatus",o.get("status",""))).upper()
  if status not in ("NEW","OPEN","ACTIVE","UNACTIVATED","UNTRIGGERED","PENDING"):continue
  if o.get("side") is not None and str(o.get("side")).upper()!=close_side:
   return {"verified":False,"reason":"CLOSING_SIDE_MISMATCH"}
  if o.get("reduceOnly") is not True:return {"verified":False,"reason":"REDUCE_ONLY_NOT_TRUE"}
  if o.get("closePosition") is True:
   raw=o.get("quantity",o.get("origQty"))
   try:raw_qty=Decimal(str(raw if raw not in (None,"") else "0"))
   except (InvalidOperation,TypeError):return {"verified":False,"reason":"BAD_CLOSE_ALL_QUANTITY"}
   if not raw_qty.is_finite() or raw_qty<0 or raw_qty>0:
    return {"verified":False,"reason":"CLOSE_ALL_QUANTITY_CONFLICT"}
   amount=qty
  else:
   if o.get("quantityUnitVerified") is not True:return {"verified":False,"reason":"UNVERIFIED_QUANTITY_UNIT"}
   amount=decimal(o.get("quantity",o.get("origQty")))
   if amount is None:return {"verified":False,"reason":"BAD_ALGO_QUANTITY"}
  grouped[kind].append(amount)
 totals={name:sum(items,Decimal(0)) for name,items in grouped.items()}
 return {"verified":True,"positionQty":str(qty),"tpCovered":totals["TAKE_PROFIT"]>=qty,
 "slCovered":totals["STOP_LOSS"]>=qty,"trailingCovered":totals["TRAILING"]>=qty,
 "totals":{k:str(v) for k,v in totals.items()},
 "note":"Verified separately by TP/SL class; closePosition maps to the full position; no orders submitted"}
