"""Inspect order-history field names and enum values only. No identifiers or balances printed."""
from collections import Counter
from monitor import query
for path in ("/capi/v3/order/history?limit=100&page=0","/capi/v3/openOrders?limit=100&page=0"):
 try:
  rows=query(path)
  if not isinstance(rows,list):raise ValueError("Unexpected response type")
  print(path,"count",len(rows),"fields",sorted(set().union(*(set(x.keys()) for x in rows))) if rows else [])
  for field in ("status","type","side","positionSide"):
   print(field,dict(Counter(str(x.get(field,"<missing>")) for x in rows)))
  print("clientOrderId_present",sum(bool(x.get("clientOrderId")) for x in rows))
 except Exception as e:print(path,"error",type(e).__name__)
