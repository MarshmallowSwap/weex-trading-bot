"""Atomic cumulative WEEX demo shadow events, role-bound and idempotent. No network."""
import sqlite3
from decimal import Decimal
from contextlib import closing
def sync(db_path, order, *, role, owner_verified):
 if not owner_verified or order.get("symbol")!="BTCSUSDT" or role not in ("ENTRY","EXIT") or order.get("positionSide") not in ("LONG","SHORT"):
  return {"accepted":False,"reason":"OWNERSHIP_OR_IDENTITY_UNVERIFIED"}
 cid=str(order.get("clientOrderId") or "");oid=str(order.get("orderId") or "")
 if not cid or not oid:return {"accepted":False,"reason":"MISSING_ID"}
 try:
  total=Decimal(str(order["origQty"]));filled=Decimal(str(order["executedQty"]))
  if not total.is_finite() or not filled.is_finite() or total<=0 or filled<0 or filled>total:raise ValueError()
 except (KeyError,ValueError,TypeError):return {"accepted":False,"reason":"INVALID_QUANTITY"}
 with closing(sqlite3.connect(db_path,timeout=10)) as db:
  db.execute("CREATE TABLE IF NOT EXISTS observed (order_id TEXT PRIMARY KEY,client_id TEXT UNIQUE,role TEXT,filled TEXT)")
  db.execute("CREATE TABLE IF NOT EXISTS shadow_position (client_id TEXT PRIMARY KEY,symbol TEXT,side TEXT,qty TEXT)")
  db.execute("BEGIN IMMEDIATE")
  previous=db.execute("SELECT client_id,role,filled FROM observed WHERE order_id=?",(oid,)).fetchone()
  if previous and (previous[0]!=cid or previous[1]!=role):
   db.rollback();return {"accepted":False,"reason":"ORDER_ID_CONFLICT"}
  before=Decimal(previous[2]) if previous else Decimal(0)
  if filled<before:
   db.rollback();return {"accepted":False,"reason":"FILL_REGRESSION"}
  delta=filled-before
  row=db.execute("SELECT qty,side FROM shadow_position WHERE client_id=?",(cid,)).fetchone()
  if delta:
   if role=="ENTRY":
    if row and row[1]!=order["positionSide"]:raise ValueError("SIDE_CONFLICT")
    new=Decimal(row[0])+delta if row else delta
    db.execute("INSERT OR REPLACE INTO shadow_position VALUES(?,?,?,?)",(cid,"BTCSUSDT",order["positionSide"],str(new)))
   else:
    if not row or row[1]!=order["positionSide"] or delta>Decimal(row[0]):
     db.rollback();return {"accepted":False,"reason":"EXIT_NOT_BOT_OWNED_OR_OVER_CLOSE"}
    db.execute("UPDATE shadow_position SET qty=? WHERE client_id=?",(str(Decimal(row[0])-delta),cid))
  db.execute("INSERT OR REPLACE INTO observed VALUES(?,?,?,?)",(oid,cid,role,str(filled)))
  db.commit()
  return {"accepted":True,"delta":str(delta),"shadowOnly":True}
