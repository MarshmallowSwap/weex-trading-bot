"""Durable read-only position snapshots and trailing observation state."""
import json,os,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"ai_positions.sqlite3"
def connect():
 c=sqlite3.connect(DB)
 c.execute("CREATE TABLE IF NOT EXISTS snapshots (symbol TEXT, side TEXT, observed_at TEXT, quantity TEXT, mark TEXT, PRIMARY KEY(symbol,side))")
 c.execute("CREATE TABLE IF NOT EXISTS extremes (symbol TEXT, side TEXT, favorable TEXT, PRIMARY KEY(symbol,side))")
 return c
def observe(symbol,side,qty,mark):
 side=side.upper()
 if side not in ("LONG","SHORT"):raise ValueError("side")
 q=Decimal(str(qty));p=Decimal(str(mark))
 if q<=0 or p<=0:raise ValueError("positive values required")
 with closing(connect()) as db, db:
  old=db.execute("SELECT favorable FROM extremes WHERE symbol=? AND side=?",(symbol,side)).fetchone()
  peak=p if old is None else (max(p,Decimal(old[0])) if side=="LONG" else min(p,Decimal(old[0])))
  db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?) ON CONFLICT(symbol,side) DO UPDATE SET observed_at=excluded.observed_at,quantity=excluded.quantity,mark=excluded.mark",(symbol,side,datetime.now(timezone.utc).isoformat(),str(q),str(p)))
  db.execute("INSERT INTO extremes VALUES (?,?,?) ON CONFLICT(symbol,side) DO UPDATE SET favorable=excluded.favorable",(symbol,side,str(peak)))
 return {"symbol":symbol,"side":side,"quantity":str(q),"mark":str(p),"favorableExtreme":str(peak),"readOnly":True}
if __name__=="__main__":print("Position Manager database initialized; no orders or account writes.")
