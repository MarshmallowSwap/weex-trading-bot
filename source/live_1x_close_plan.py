"""Build WEEX live-pilot closing request safely. No network calls."""
def plan_close(position,*,bot_owned_position_id,bot_order_reconciled=False):
 if not bot_order_reconciled:return {"allowed":False,"reason":"ORDER_NOT_RECONCILED"}
 if not isinstance(position,dict):return {"allowed":False,"reason":"INVALID_POSITION"}
 pid=position.get("id")
 if not isinstance(pid,(str,int)) or not str(pid).isdigit() or str(pid)=="0":
  return {"allowed":False,"reason":"INVALID_POSITION_ID"}
 if str(pid)!=str(bot_owned_position_id):
  return {"allowed":False,"reason":"POSITION_NOT_BOT_OWNED"}
 if position.get("manualOrMixed") is not False:return {"allowed":False,"reason":"MANUAL_OR_MIXED"}
 if position.get("marginType") not in ("CROSSED","CROSS"):
  return {"allowed":False,"reason":"NOT_CROSS"}
 symbol=position.get("symbol")
 if not isinstance(symbol,str) or not symbol.endswith("USDT"):
  return {"allowed":False,"reason":"INVALID_SYMBOL"}
 return {"allowed":True,"endpoint":"/capi/v3/closePositions",
         "payload":{"symbol":symbol,"positionId":str(pid)},"submitted":False}
