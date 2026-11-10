"""Fail-closed live 1x close preflight: validated account position ID and bot attribution.
No network write calls.
"""
from live_1x_close_plan import plan_close
def evaluate(position,bot_order,*,snapshot_fresh,preexisting_symbol_free,entry_fill_verified,order_client_bound):
 if not snapshot_fresh:return {"allowed":False,"reason":"STALE_SNAPSHOT"}
 if not preexisting_symbol_free:return {"allowed":False,"reason":"EXISTING_MANUAL_EXPOSURE"}
 if not entry_fill_verified or not order_client_bound:return {"allowed":False,"reason":"BOT_ENTRY_NOT_VERIFIED"}
 if position.get("manualOrMixed") is not False:return {"allowed":False,"reason":"MANUAL_MIX_RISK"}
 if bot_order.get("symbol")!=position.get("symbol") or bot_order.get("positionSide")!=position.get("side"):
  return {"allowed":False,"reason":"SYMBOL_SIDE_MISMATCH"}
 # Full provenance cannot be established from symbol+side alone.
 return {"allowed":False,"reason":"EXCHANGE_POSITION_ATTRIBUTION_UNCERTIFIED","ordersSubmitted":False}
