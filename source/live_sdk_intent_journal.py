"""LIVE SDK submission-intent journal. No exchange writes.
Atomic reservation forbids resending any previously reserved client identifier.
"""
import sqlite3,uuid
from pathlib import Path
from contextlib import closing
DB=Path(__file__).with_name("live_sdk_intent_journal.sqlite3")
def connect(path=None):
 db=sqlite3.connect(str(path or DB),timeout=10)
 db.execute("CREATE TABLE IF NOT EXISTS reservations (signal_id TEXT PRIMARY KEY,client_id TEXT NOT NULL UNIQUE,symbol TEXT NOT NULL,state TEXT NOT NULL)")
 return db
def reserve(signal_id,symbol,db_path=None):
 if not signal_id or symbol!="ETHUSDT":raise ValueError("INVALID_PILOT_SCOPE")
 with closing(connect(db_path)) as db:
  db.execute("BEGIN IMMEDIATE")
  row=db.execute("SELECT client_id,state FROM reservations WHERE signal_id=?",(signal_id,)).fetchone()
  if row:
   db.rollback()
   return {"clientOrderId":row[0],"state":row[1],"canSend":False,"reason":"EXISTING_RESERVATION"}
  client="wxpilot_"+uuid.uuid4().hex[:25]
  db.execute("INSERT INTO reservations VALUES(?,?,?,'RESERVED')",(signal_id,client,symbol))
  db.commit()
  return {"clientOrderId":client,"state":"RESERVED","canSend":False}
def mark_unknown(signal_id,db_path=None):
 with closing(connect(db_path)) as db,db:
  return db.execute("UPDATE reservations SET state='SUBMISSION_UNKNOWN' WHERE signal_id=? AND state='RESERVED'",(signal_id,)).rowcount==1
