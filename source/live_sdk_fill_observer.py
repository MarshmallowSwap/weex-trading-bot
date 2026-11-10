"""LIVE SDK fill observation only: exact exchange IDs, bounded, no position mutation."""
from decimal import Decimal,InvalidOperation
def reconcile_fills(orders,trades,reservations):
 if not all(isinstance(x,list) for x in (orders,trades,reservations)):
  return {"valid":False,"reason":"INVALID_INPUT"}
 by_order={}
 for o in orders:
  oid=str(o.get("orderId") or "")
  if oid:by_order.setdefault(oid,[]).append(o)
 results=[]
 for b in reservations:
  client=b.get("clientOrderId")
  if not client:continue
  matched=[o for o in orders if o.get("clientOrderId")==client]
  if len(matched)!=1:
   results.append({"clientOrderId":client,"state":"UNRESOLVED_ORDER","canAct":False});continue
  o=matched[0];oid=str(o.get("orderId") or "")
  if not oid or len(by_order.get(oid,[]))!=1:
   results.append({"clientOrderId":client,"state":"AMBIGUOUS_ID","canAct":False});continue
  seen=set();total=Decimal(0);valid=True
  for t in trades:
   if str(t.get("orderId") or "")!=oid:continue
   tid=str(t.get("id") or "")
   if not tid or tid in seen:valid=False;break
   seen.add(tid)
   try:
    q=Decimal(str(t["qty"]))
    if not q.is_finite() or q<=0:raise ValueError()
    total+=q
   except (ValueError,InvalidOperation,TypeError,KeyError):valid=False;break
  try:
   filled=Decimal(str(o["executedQty"]))
   if not filled.is_finite() or filled<0 or total!=filled:valid=False
  except (ValueError,InvalidOperation,TypeError,KeyError):valid=False
  results.append({"clientOrderId":client,"state":"OBSERVED_MATCH" if valid else "FILL_MISMATCH",
                  "matchedFills":len(seen),"filledQty":str(total),"canAct":False})
 return {"valid":True,"observations":results,"canPlaceOrders":False,"canClosePositions":False}
