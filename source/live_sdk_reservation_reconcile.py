"""Reconcile LIVE pilot reservations against WEEX order observations. Read-only.
Missing history is unresolved, not proof that submitting again is safe.
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from live_sdk_intent_journal import DB
def inspect(history,open_orders,db_path=None):
 if not isinstance(history,list) or not isinstance(open_orders,list):
  return {"safe":False,"reason":"INVALID_EXCHANGE_SNAPSHOT","items":[]}
 db=Path(db_path or DB)
 if not db.exists():return {"safe":True,"items":[],"canRetryUnknown":False}
 with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro",uri=True)) as c:
  reservations=c.execute("SELECT signal_id,client_id,symbol,state FROM reservations").fetchall()
 rows=history+open_orders
 items=[]
 for signal,client,symbol,state in reservations:
  matches=[x for x in rows if x.get("clientOrderId")==client]
  if len(matches)>1:
   status="AMBIGUOUS"
  elif len(matches)==0:
   status="UNRESOLVED_NOT_FOUND"
  elif matches[0].get("symbol")!=symbol or not matches[0].get("orderId"):
   status="INVALID_EXCHANGE_BINDING"
  else:
   status="EXCHANGE_ORDER_OBSERVED"
  items.append({"signalId":signal,"clientOrderId":client,"localState":state,
                "reconciliation":status,"canRetry":False,"canClose":False})
 return {"safe":not any(x["reconciliation"] in ("AMBIGUOUS","INVALID_EXCHANGE_BINDING") for x in items),
         "items":items,"canRetryUnknown":False,"writes":False}
