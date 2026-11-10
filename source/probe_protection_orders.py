"""Read WEEX conditional orders without order placement; show only schema/count."""
from monitor import query
for route in ("/capi/v3/openAlgoOrders?limit=100&page=1","/capi/v3/trailing/openOrders?limit=100&page=0"):
 try:
  r=query(route)
  print(route,"shape",type(r).__name__,"count",len(r) if isinstance(r,list) else -1)
  if isinstance(r,list) and r:print("field_names",sorted(r[0].keys()))
 except Exception as e:print(route,"error",type(e).__name__,"http",getattr(e,"code","NA"))
