"""Local order lifecycle state machine. No network or trade execution."""
import sqlite3,uuid,json
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
DB=Path(__file__).with_name("execution_lifecycle.sqlite3")
ALLOWED={
 "CREATED":{"RISK_REJECTED","APPROVED"},
 "APPROVED":{"SUBMISSION_UNKNOWN","CANCELLED"},
 "SUBMISSION_UNKNOWN":{"ACKNOWLEDGED","RECONCILIATION_REQUIRED"},
 "ACKNOWLEDGED":{"OPEN","PARTIAL","FILLED","CANCELLED","RECONCILIATION_REQUIRED"},
 "OPEN":{"PARTIAL","FILLED","CANCELLED","RECONCILIATION_REQUIRED"},
 "PARTIAL":{"PARTIAL","FILLED","CANCELLED","RECONCILIATION_REQUIRED"},
 "RECONCILIATION_REQUIRED":{"ACKNOWLEDGED","OPEN","PARTIAL","FILLED","CANCELLED"},
 "FILLED":set(),"CANCELLED":set(),"RISK_REJECTED":set()
}
def connect(path=None):
 c=sqlite3.connect(path or DB,timeout=10)
 c.execute("PRAGMA foreign_keys=ON")
 c.execute("CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,state TEXT NOT NULL,created_at TEXT NOT NULL)")
 c.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL,old_state TEXT,new_state TEXT NOT NULL,at TEXT NOT NULL,FOREIGN KEY(id) REFERENCES orders(id))")
 return c
def create(path=None,identity=None):
 ident=identity or str(uuid.uuid4());at=datetime.now(timezone.utc).isoformat()
 with closing(connect(path)) as db,db:
  db.execute("INSERT OR IGNORE INTO orders VALUES(?,?,?)",(ident,"CREATED",at))
  db.execute("INSERT INTO events(id,old_state,new_state,at) SELECT ?,NULL,'CREATED',? WHERE NOT EXISTS(SELECT 1 FROM events WHERE id=?)",(ident,at,ident))
 return ident
def transition(ident,new,path=None):
 if new not in ALLOWED:raise ValueError("Unknown state")
 with closing(connect(path)) as db,db:
  old=db.execute("SELECT state FROM orders WHERE id=?",(ident,)).fetchone()
  if old is None:raise ValueError("Unknown order")
  current=old[0]
  if new==current:return False
  if new not in ALLOWED[current]:raise ValueError("Invalid transition: "+current+" -> "+new)
  db.execute("UPDATE orders SET state=? WHERE id=?",(new,ident))
  db.execute("INSERT INTO events(id,old_state,new_state,at) VALUES(?,?,?,?)",(ident,current,new,datetime.now(timezone.utc).isoformat()))
 return True
def timeline(ident,path=None):
 with closing(connect(path)) as db:
  return db.execute("SELECT old_state,new_state FROM events WHERE id=? ORDER BY seq",(ident,)).fetchall()
