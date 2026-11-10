"""Persistent shadow position lifecycle for WEEX demo; NO EXCHANGE ORDER ROUTES."""
import sqlite3
from decimal import Decimal
from pathlib import Path
from contextlib import closing
DB=Path(__file__).with_name("demo_shadow_lifecycle.sqlite3")
def open_db(path=None):
 c=sqlite3.connect(str(path or DB))
 c.execute("CREATE TABLE IF NOT EXISTS positions (client_id TEXT PRIMARY KEY,symbol TEXT,side TEXT,opened TEXT,remaining TEXT,closed TEXT,ownership TEXT)")
 return c
def apply(client_id,symbol,side,event,quantity,db_path=None):
 q=Decimal(str(quantity))
 if not q.is_finite() or q<=0:raise ValueError("INVALID_QUANTITY")
 if symbol!="BTCSUSDT" or side not in ("LONG","SHORT"):raise ValueError("INVALID_DEMO_CONTRACT")
 if event not in ("ENTRY_FILL","EXIT_FILL"):raise ValueError("INVALID_EVENT")
 with closing(open_db(db_path)) as c,c:
  row=c.execute("SELECT opened,remaining,closed,ownership FROM positions WHERE client_id=?",(client_id,)).fetchone()
  if event=="ENTRY_FILL":
   if row:raise ValueError("DUPLICATE_OR_MIXED_ENTRY")
   c.execute("INSERT INTO positions VALUES (?,?,?,?,?,?,?)",(client_id,symbol,side,str(q),str(q),"0","BOT_SHADOW"))
   return {"state":"OPEN","remaining":str(q)}
  if not row or row[3]!="BOT_SHADOW":raise ValueError("UNOWNED_POSITION")
  opened,remaining,closed=map(Decimal,row[:3])
  if q>remaining:raise ValueError("EXIT_EXCEEDS_POSITION")
  remaining-=q;closed+=q
  c.execute("UPDATE positions SET remaining=?,closed=? WHERE client_id=?",(str(remaining),str(closed),client_id))
  return {"state":"CLOSED" if remaining==0 else "PARTIAL","remaining":str(remaining)}
def snapshot(db_path=None):
 with closing(open_db(db_path)) as c:return c.execute("SELECT client_id,symbol,side,remaining,ownership FROM positions").fetchall()
