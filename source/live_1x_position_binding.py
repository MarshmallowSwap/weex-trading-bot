"""Pilot live position ownership binding. Pure fail-closed; NEVER sends orders."""
def reconcile_position(position, bot_order, *, manual_exposure_before, fresh_snapshot):
 if not fresh_snapshot:return {"verified":False,"reason":"STALE_POSITION_SNAPSHOT"}
 if not isinstance(position,dict) or not isinstance(bot_order,dict):return {"verified":False,"reason":"MISSING_EVIDENCE"}
 if manual_exposure_before is not False:return {"verified":False,"reason":"PREEXISTING_EXPOSURE_UNKNOWN"}
 if bot_order.get("verified") is not True or bot_order.get("status") not in ("FILLED","PARTIAL"):
  return {"verified":False,"reason":"BOT_ORDER_NOT_VERIFIED"}
 if not bot_order.get("clientOrderId") or not bot_order.get("orderId"):
  return {"verified":False,"reason":"MISSING_ORDER_BINDING"}
 if position.get("symbol")!=bot_order.get("symbol") or position.get("side")!=bot_order.get("positionSide"):
  return {"verified":False,"reason":"SYMBOL_OR_SIDE_MISMATCH"}
 pid=position.get("positionId")
 if not pid or not str(pid).isdigit():return {"verified":False,"reason":"INVALID_POSITION_ID"}
 if position.get("manualOrMixed") is not False:return {"verified":False,"reason":"MIXED_POSITION"}
 return {"verified":False,"reason":"EXCHANGE_POSITION_PROVENANCE_NOT_ESTABLISHED",
         "candidatePositionId":str(pid),"closeAuthorized":False}
