"""Durable demo intent binding. Offline only. Unknown send outcome cannot be retried."""
import sqlite3,uuid,re
from contextlib import closing
from pathlib import Path
DB=Path(__file__).with_name("demo_intents.sqlite3")
def connect(db=None):
 c=sqlite3.connect(str(db or DB),timeout=10)
 c.execute("CREATE TABLE IF NOT EXISTS demo_intents (client_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,state TEXT NOT NULL,exchange_id TEXT UNIQUE)")
 return c
def register(symbol,client_id=None,db=None):
 if symbol!="BTCSUSDT":raise ValueError("NOT_ALLOWLISTED")
 client_id=client_id or "wxd_"+uuid.uuid4().hex[:28]
 if not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,36}",client_id):raise ValueError("INVALID_CLIENT_ID")
 with closing(connect(db)) as c,c:
  c.execute("INSERT INTO demo_intents(client_id,symbol,state) VALUES(?,?,'PREPARED')",(client_id,symbol))
 return client_id
def uncertain(client_id,db=None):
 with closing(connect(db)) as c,c:
  row=c.execute("UPDATE demo_intents SET state='SUBMISSION_UNKNOWN' WHERE client_id=? AND state='PREPARED'",(client_id,))
  return row.rowcount==1
def reconcile(client_id,exchange_orders,db=None):
 matches=[o for o in exchange_orders if str(o.get("clientOrderId"))==client_id]
 if len(matches)!=1 or not matches[0].get("orderId"):return False
 exchange_id=str(matches[0]["orderId"])
 with closing(connect(db)) as c,c:
  row=c.execute("UPDATE demo_intents SET state='ACKNOWLEDGED',exchange_id=? WHERE client_id=? AND state='SUBMISSION_UNKNOWN'",(exchange_id,client_id))
  return row.rowcount==1
