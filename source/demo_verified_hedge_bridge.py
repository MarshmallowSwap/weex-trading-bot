"""Strict verified demo order bridge to multi-order Hedge shadow ledger.
Only registered persistent intents with verified exchange ID may be applied.
No live/demo order network writes.
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from verified_order_state_sync import validate
from demo_hedge_multiorder import apply
def bridge(orders, client_id, role, *,intent_db,hedge_db):
 if role not in ("ENTRY","EXIT"):return {"accepted":False,"reason":"INVALID_ROLE"}
 with closing(sqlite3.connect(intent_db)) as db:
  binding=db.execute("SELECT symbol,state,exchange_id FROM demo_intents WHERE client_id=?",(client_id,)).fetchone()
 if not binding or binding[0]!="BTCSUSDT" or binding[1]!="ACKNOWLEDGED" or not binding[2]:
  return {"accepted":False,"reason":"NO_VERIFIED_PERSISTENT_BINDING"}
 v=validate(client_id,orders)
 if not v.get("verified") or v["orderId"]!=str(binding[2]):
  return {"accepted":False,"reason":"ORDER_MISMATCH_OR_INVALID"}
 matches=[o for o in orders if str(o.get("clientOrderId") or "")==client_id]
 if len(matches)!=1:return {"accepted":False,"reason":"DUPLICATE_ORDER"}
 o=matches[0]
 if o.get("symbol")!="BTCSUSDT":return {"accepted":False,"reason":"NOT_DEMO"}
 side=o.get("positionSide")
 direction=o.get("side")
 if side not in ("LONG","SHORT"):return {"accepted":False,"reason":"BAD_SIDE"}
 expected=("BUY" if side=="LONG" else "SELL") if role=="ENTRY" else ("SELL" if side=="LONG" else "BUY")
 if direction!=expected:return {"accepted":False,"reason":"ROLE_SIDE_MISMATCH"}
 # Source provenance is verified, but demo exchange executions are still synthetic in unit tests.
 return apply(hedge_db,o,role,True)
