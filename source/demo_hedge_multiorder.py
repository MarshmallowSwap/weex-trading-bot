"""Multi-order hedge shadow ledger. Isolated demo-only, no exchange calls."""
import sqlite3
from decimal import Decimal, InvalidOperation
from contextlib import closing
def apply(db_path,order,role,owned):
 if owned is not True or role not in ("ENTRY","EXIT") or order.get("symbol")!="BTCSUSDT" or order.get("positionSide") not in ("LONG","SHORT"):
  return {"accepted":False,"reason":"NOT_VERIFIED_DEMO_BOT_ORDER"}
 client=str(order.get("clientOrderId") or ""); oid=str(order.get("orderId") or "")
 if not client or not oid:return {"accepted":False,"reason":"MISSING_IDS"}
 try:
  total=Decimal(str(order["origQty"]));filled=Decimal(str(order["executedQty"]))
  if not total.is_finite() or not filled.is_finite() or total<=0 or not 0<=filled<=total:raise ValueError
 except (ValueError,InvalidOperation,KeyError,TypeError):return {"accepted":False,"reason":"BAD_QTY"}
 key=("BTCSUSDT",order["positionSide"])
 with closing(sqlite3.connect(db_path,timeout=10)) as db:
  db.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, client_id TEXT UNIQUE, role TEXT, side TEXT, filled TEXT)")
  db.execute("CREATE TABLE IF NOT EXISTS hedge (symbol TEXT, side TEXT, qty TEXT, PRIMARY KEY(symbol,side))")
  db.execute("BEGIN IMMEDIATE")
  old=db.execute("SELECT client_id,role,side,filled FROM orders WHERE order_id=?",(oid,)).fetchone()
  if old and old[:3]!=(client,role,key[1]):return {"accepted":False,"reason":"ORDER_ID_CONFLICT"}
  before=Decimal(old[3]) if old else Decimal(0)
  if filled<before:return {"accepted":False,"reason":"FILL_REGRESSION"}
  delta=filled-before
  row=db.execute("SELECT qty FROM hedge WHERE symbol=? AND side=?",key).fetchone()
  previous=Decimal(row[0]) if row else Decimal(0)
  after=previous+delta if role=="ENTRY" else previous-delta
  if after<0:return {"accepted":False,"reason":"UNOWNED_OR_OVER_CLOSE"}
  db.execute("INSERT INTO hedge VALUES(?,?,?) ON CONFLICT(symbol,side) DO UPDATE SET qty=excluded.qty",(*key,str(after)))
  db.execute("INSERT INTO orders VALUES(?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET filled=excluded.filled",(oid,client,role,key[1],str(filled)))
  db.commit()
  return {"accepted":True,"delta":str(delta),"positionQty":str(after),"shadowOnly":True}
