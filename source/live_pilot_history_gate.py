"""WEEX LIVE pilot read-only reconciliation gate.
Historical order coverage does NOT imply bot ownership. Incomplete history fails closed.
"""
def assess(trades,history,bot_bindings,*,history_complete,positions_fresh):
 if not isinstance(trades,list) or not isinstance(history,list) or not isinstance(bot_bindings,list):
  return {"certified":False,"reason":"INVALID_INPUT"}
 if not history_complete or not positions_fresh:return {"certified":False,"reason":"INCOMPLETE_OR_STALE"}
 byid={}
 for o in history:
  key=str(o.get("orderId") or "")
  if key:byid.setdefault(key,[]).append(o)
 missing=[]
 for t in trades:
  k=str(t.get("orderId") or "")
  if len(byid.get(k,[]))!=1:missing.append(k)
 bound={str(x.get("orderId")):x for x in bot_bindings if x.get("verified") is True and x.get("clientOrderId") and x.get("orderId")}
 verified=[]
 for oid,b in bound.items():
  matches=byid.get(oid,[])
  if len(matches)==1 and str(matches[0].get("clientOrderId") or "")==str(b["clientOrderId"]):
   verified.append(oid)
 return {"certified":False,"reason":"LIVE_BOT_ORDER_CYCLE_NOT_VERIFIED",
 "matchedHistoryTrades":len(trades)-len(missing),"unmatchedHistoryTrades":len(missing),
 "verifiedBotOrderIds":verified,"canClosePosition":False,"canSubmitOrder":False}
