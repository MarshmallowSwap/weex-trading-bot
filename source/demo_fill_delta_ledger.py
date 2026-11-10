"""Atomic, idempotent synthetic fill ledger. Shadow only; no exchange calls."""
import sqlite3
from decimal import Decimal,InvalidOperation
from contextlib import closing
def apply(db_path,*,execution_id,client_id,symbol,position_side,role,qty):
 if not execution_id or not client_id or symbol!="BTCSUSDT" or position_side not in ("LONG","SHORT") or role not in ("ENTRY","EXIT"):
  raise ValueError("INVALID_IDENTITY")
 try:
  q=Decimal(str(qty))
  if not q.is_finite() or q<=0:raise ValueError()
 except (InvalidOperation,ValueError,TypeError):raise ValueError("INVALID_QTY")
 with closing(sqlite3.connect(db_path,timeout=10)) as db:
  db.execute("CREATE TABLE IF NOT EXISTS fills (execution_id TEXT PRIMARY KEY,client_id TEXT NOT NULL,role TEXT NOT NULL,qty TEXT NOT NULL)")
  db.execute("CREATE TABLE IF NOT EXISTS positions (client_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,side TEXT NOT NULL,remaining TEXT NOT NULL)")
  db.execute("BEGIN IMMEDIATE")
  prior=db.execute("SELECT client_id,role,qty FROM fills WHERE execution_id=?",(execution_id,)).fetchone()
  if prior:
   if prior!=(client_id,role,str(q)):raise ValueError("CONFLICTING_DUPLICATE")
   db.rollback();return {"applied":False,"reason":"DUPLICATE_FILL"}
  row=db.execute("SELECT symbol,side,remaining FROM positions WHERE client_id=?",(client_id,)).fetchone()
  if role=="ENTRY":
   if row:raise ValueError("SECOND_ENTRY_REQUIRES_SEPARATE_ORDER_MAPPING")
   remaining=q
   db.execute("INSERT INTO positions VALUES (?,?,?,?)",(client_id,symbol,position_side,str(remaining)))
  else:
   if not row or row[0]!=symbol or row[1]!=position_side:raise ValueError("UNOWNED_OR_MISMATCHED_POSITION")
   remaining=Decimal(row[2])-q
   if remaining<0:raise ValueError("OVER_CLOSE")
   db.execute("UPDATE positions SET remaining=? WHERE client_id=?",(str(remaining),client_id))
  db.execute("INSERT INTO fills VALUES (?,?,?,?)",(execution_id,client_id,role,str(q)))
  db.commit()
  return {"applied":True,"remaining":str(remaining),"mode":"OFFLINE_SHADOW"}
