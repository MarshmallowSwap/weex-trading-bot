"""Deterministic WEEX clientOrderId binding and fill review; no exchange order calls."""
import sqlite3
from contextlib import closing
from decimal import Decimal,InvalidOperation
from execution_intent_ledger import connect
def bind_client_id(intent_id,client_id,db_path=None):
 if not client_id or len(client_id)>64:raise ValueError("Invalid client ID")
 with closing(connect(db_path)) as db,db:
  db.execute("CREATE TABLE IF NOT EXISTS client_bindings(intent_id TEXT PRIMARY KEY,client_id TEXT NOT NULL UNIQUE)")
  row=db.execute("SELECT state FROM intents WHERE intent_id=?",(intent_id,)).fetchone()
  if not row:raise ValueError("Unknown intent")
  old=db.execute("SELECT client_id FROM client_bindings WHERE intent_id=?",(intent_id,)).fetchone()
  if old and old[0]!=client_id:raise ValueError("Immutable binding")
  db.execute("INSERT OR IGNORE INTO client_bindings VALUES (?,?)",(intent_id,client_id))
 return {"intentId":intent_id,"clientOrderId":client_id,"canSubmit":False}
def review_fills(client_id,orders):
 matched=[o for o in orders if str(o.get("clientOrderId") or "")==client_id]
 if len(matched)!=1:return {"state":"UNKNOWN","reason":"Missing or ambiguous client ID","canSubmit":False}
 o=matched[0]
 try:
  original=Decimal(str(o["origQty"]));executed=Decimal(str(o["executedQty"]))
  if not original.is_finite() or not executed.is_finite() or original<=0 or executed<0 or executed>original:raise ValueError()
 except (KeyError,InvalidOperation,ValueError,TypeError):
  return {"state":"UNKNOWN","reason":"Invalid fill quantities","canSubmit":False}
 if executed==original:state="FILLED"
 elif executed>0:state="PARTIAL"
 else:state="UNFILLED"
 return {"state":state,"original":str(original),"executed":str(executed),"remaining":str(original-executed),"canSubmit":False}
