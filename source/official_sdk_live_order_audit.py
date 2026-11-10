"""Independent cross-source WEEX live order inventory: read-only, fail-closed."""
from collections import Counter
def audit(orders,trades,bindings):
 if not all(isinstance(v,list) for v in (orders,trades,bindings)):return {"certified":False,"reason":"BAD_INPUT"}
 ids=[str(o.get("orderId")) for o in orders if o.get("orderId")]
 duplicates={k for k,v in Counter(ids).items() if v>1}
 byid={str(o.get("orderId")):o for o in orders if o.get("orderId") and str(o.get("orderId")) not in duplicates}
 unmatched=[str(t.get("orderId")) for t in trades if str(t.get("orderId")) not in byid]
 matched=[]
 for b in bindings:
  oid=str(b.get("orderId") or "")
  row=byid.get(oid)
  if b.get("verified") is True and oid and row and row.get("clientOrderId")==b.get("clientOrderId"):
   matched.append(oid)
 return {"certified":False,"historicalOrders":len(orders),"trades":len(trades),
  "duplicateOrderIds":sorted(duplicates),"unmatchedTradeCount":len(unmatched),
  "botBindingsMatched":sorted(set(matched)),"canSubmit":False,"canClose":False}
