"""WEEX execution intent ledger: no network calls, no order placement."""
import sqlite3,json,hashlib,uuid
from contextlib import closing
from pathlib import Path
from datetime import datetime,timezone
DB=Path(__file__).with_name("execution_intents.sqlite3")
def connect(path=None):
 c=sqlite3.connect(path or DB,timeout=10)
 c.execute("CREATE TABLE IF NOT EXISTS intents (intent_id TEXT PRIMARY KEY, dedup_key TEXT NOT NULL UNIQUE, symbol TEXT NOT NULL, side TEXT NOT NULL, margin TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL)")
 return c
def register(symbol,side,margin,signal_id,db_path=None):
 if side not in ("LONG","SHORT") or not symbol or not signal_id:raise ValueError("Invalid intent")
 from decimal import Decimal
 if Decimal(str(margin))<=0:raise ValueError("Invalid margin")
 dedup=hashlib.sha256(json.dumps([signal_id,symbol,side],separators=(",",":")).encode()).hexdigest()
 with closing(connect(db_path)) as db,db:
  db.execute("INSERT OR IGNORE INTO intents VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),dedup,symbol,side,str(margin),"PENDING_REVIEW",datetime.now(timezone.utc).isoformat()))
  item=db.execute("SELECT intent_id,state FROM intents WHERE dedup_key=?",(dedup,)).fetchone()
 return {"intentId":item[0],"state":item[1],"dedupKey":dedup,"canSubmitToExchange":False}
def mark_uncertain(intent_id,db_path=None):
 with closing(connect(db_path)) as db,db:
  cur=db.execute("UPDATE intents SET state='UNKNOWN_RECONCILIATION_REQUIRED' WHERE intent_id=? AND state='PENDING_REVIEW'",(intent_id,))
  return cur.rowcount
