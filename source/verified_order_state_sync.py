"""Apply only uniquely matched, verified WEEX order observations to local lifecycle.
No exchange writes. Uncertain observations never advance state.
"""
from decimal import Decimal,InvalidOperation
from execution_lifecycle import create,transition,timeline
STATUS={"NEW":"OPEN","OPEN":"OPEN","PARTIALLY_FILLED":"PARTIAL","PARTIAL_FILLED":"PARTIAL",
        "FILLED":"FILLED","FULLY_FILLED":"FILLED","CANCELED":"CANCELLED","CANCELLED":"CANCELLED"}
def validate(client_id,records):
 if not client_id:return {"verified":False,"reason":"NO_CLIENT_ID"}
 matches=[x for x in records if str(x.get("clientOrderId") or "")==str(client_id)]
 if len(matches)!=1:return {"verified":False,"reason":"MISSING_OR_DUPLICATE"}
 o=matches[0]
 if not o.get("orderId"):return {"verified":False,"reason":"MISSING_EXCHANGE_ID"}
 try:
  total=Decimal(str(o["origQty"]));filled=Decimal(str(o["executedQty"]))
  if not all(x.is_finite() for x in (total,filled)) or total<=0 or filled<0 or filled>total:raise ValueError()
 except (KeyError,TypeError,ValueError,InvalidOperation):
  return {"verified":False,"reason":"INVALID_QUANTITY"}
 status=str(o.get("status","")).upper()
 mapped=STATUS.get(status)
 if mapped is None:return {"verified":False,"reason":"UNKNOWN_EXCHANGE_STATE"}
 if mapped=="FILLED" and filled!=total:return {"verified":False,"reason":"INCONSISTENT_FILL"}
 if mapped=="PARTIAL" and not (0<filled<total):return {"verified":False,"reason":"INCONSISTENT_PARTIAL"}
 return {"verified":True,"target":mapped,"orderId":str(o["orderId"]),"filled":str(filled),"total":str(total)}
def apply(intent_id,client_id,orders,db_path=None,intent_db_path=None):
 observation=validate(client_id,orders)
 if not observation["verified"]:return {"applied":False,"observation":observation}
 # Require an immutable local binding, never trust only supplied callback parameters.
 from execution_intent_ledger import connect as intent_connect
 from contextlib import closing
 with closing(intent_connect(intent_db_path)) as ids:
  ids.execute("CREATE TABLE IF NOT EXISTS client_bindings(intent_id TEXT PRIMARY KEY,client_id TEXT NOT NULL UNIQUE)")
  bound=ids.execute("SELECT client_id FROM client_bindings WHERE intent_id=?",(intent_id,)).fetchone()
 if not bound or bound[0]!=client_id:return {"applied":False,"reason":"UNBOUND_CLIENT_ID"}
 from execution_lifecycle import connect
 from contextlib import closing
 with closing(connect(db_path)) as db:
  row=db.execute("SELECT state FROM orders WHERE id=?",(intent_id,)).fetchone()
 if not row:return {"applied":False,"reason":"UNKNOWN_LOCAL_INTENT"}
 target=observation["target"]
 try:
  changed=transition(intent_id,target,db_path)
 except ValueError:
  return {"applied":False,"reason":"INVALID_STATE_TRANSITION","observation":observation}
 return {"applied":changed,"observation":observation,"timeline":timeline(intent_id,db_path)}
