"""Conservative reboot recovery audit for local WEEX intents; read-only."""
import json
from contextlib import closing
from execution_intent_ledger import connect
from weex_order_pagination import history
from monitor import query
def audit():
 h=history()
 active=query("/capi/v3/openOrders?limit=100&page=0")
 if not isinstance(active,list):raise ValueError("Active order shape")
 combined=h["orders"]+active
 with closing(connect()) as db:
  db.execute("CREATE TABLE IF NOT EXISTS client_bindings(intent_id TEXT PRIMARY KEY,client_id TEXT UNIQUE NOT NULL)")
  rows=db.execute("SELECT i.intent_id,i.state,b.client_id FROM intents i LEFT JOIN client_bindings b ON b.intent_id=i.intent_id").fetchall()
 assessments=[]
 for intent,state,client_id in rows:
  matches=[o for o in combined if client_id and str(o.get("clientOrderId") or "")==client_id]
  ids={str(o.get("orderId")) for o in matches}
  assessments.append({"intentId":intent,"clientIdBound":bool(client_id),
       "state":"UNRESOLVED" if not client_id or len(ids)!=1 else "MATCH_FOUND",
       "noAutomaticResubmission":True})
 return {"historicalCount":len(h["orders"]),"currentCount":len(active),"intents":assessments,
         "historyBoundedComplete":h["completeWithinRequestedBounds"],"executionAllowed":False}
if __name__=="__main__":
 r=audit()
 print("historical",r["historicalCount"],"current",r["currentCount"],"localIntents",len(r["intents"]),"execution",r["executionAllowed"])
