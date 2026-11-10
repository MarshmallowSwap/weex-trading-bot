"""Demo hedge close attribution: require same bot-owned hedge position and bound close order.
No exchange mutations, no synthetic certification claims.
"""
import sqlite3
from contextlib import closing
from demo_verified_hedge_bridge import bridge
def apply_close(orders,client_id,*,intent_db,hedge_db):
 with closing(sqlite3.connect(hedge_db)) as db:
  row=db.execute("SELECT qty FROM hedge WHERE symbol=? AND side=?",("BTCSUSDT","LONG")).fetchone() if client_id else None
 # A live position may include manual contributions. Without exchange-side provenance,
 # local size alone cannot prove safe close-only ownership.
 if not row:return {"accepted":False,"reason":"NO_BOT_HEDGE_STATE"}
 return {"accepted":False,"reason":"MIXED_POSITION_OR_CLOSE_ONLY_NOT_VERIFIED","ordersSent":False}
