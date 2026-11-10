"""Fail-closed ownership gate for WEEX execution/exit agents.
Manual and unbound exchange positions are never controlled by this bot.
"""
def authorize(action,position,bindings,*,reconciled=False):
 if action not in ("MONITOR","CLOSE","MODIFY_PROTECTION"):
  return {"allowed":False,"reason":"UNKNOWN_ACTION"}
 if action=="MONITOR":return {"allowed":True,"reason":"READ_ONLY"}
 if not reconciled:return {"allowed":False,"reason":"UNRECONCILED"}
 key=(position.get("symbol"),position.get("positionSide"))
 if not all(key):return {"allowed":False,"reason":"MISSING_POSITION_IDENTITY"}
 matched=[b for b in bindings if b.get("symbol")==key[0] and b.get("positionSide")==key[1] and b.get("source")=="BOT" and b.get("exchangeOrderId") and b.get("clientOrderId") and b.get("verified") is True]
 if len(matched)!=1:return {"allowed":False,"reason":"NO_UNIQUE_VERIFIED_BOT_BINDING"}
 if position.get("manualOrMixed") is not False:return {"allowed":False,"reason":"MANUAL_OR_MIXED_POSITION"}
 return {"allowed":True,"reason":"VERIFIED_BOT_OWNED"}
