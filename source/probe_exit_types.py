from monitor import query
res=query("/capi/v3/order/history?limit=30&page=0")
print("HISTORY",len(res),type(res).__name__)
for o in res[-12:]:
 print("ORDER", {k:o.get(k) for k in ("symbol","orderId","type","status","side","positionSide","reduceOnly","stopPrice","closePosition","time","updateTime")})
a=query("/capi/v3/allAlgoOrders?limit=30")
print("ALGOS_SHAPE",list(a.keys()) if isinstance(a,dict) else type(a).__name__)
for o in a.get("orders",[])[:8]:
 print("ALGO", {k:o.get(k) for k in ("symbol","algoId","orderId","type","algoType","status","side","positionSide","stopPrice","triggerPrice","reduceOnly")}, "KEYS",list(o.keys())[:30])
