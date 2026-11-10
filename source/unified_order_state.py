"""Read-only unified order intent lifecycle and fill reconciliation."""
from pathlib import Path
from execution_intent_ledger import register
from execution_lifecycle import create,transition,timeline
from client_order_reconciliation import review_fills,bind_client_id
def reconcile_local(signal_id,symbol,side,margin,client_id=None,orders=None,intent_db=None,lifecycle_db=None):
 intent=register(symbol,side,margin,signal_id,intent_db)
 ident=intent["intentId"]
 create(lifecycle_db,ident)
 if client_id:
  bind_client_id(ident,client_id,intent_db)
  result=review_fills(client_id,orders or [])
  # A local association does not prove exchange submission.
  # Record observations only after explicit exchange match; no APPROVED/SUBMISSION states fabricated.
  return {"intentId":ident,"observedFill":result,"lifecycle":timeline(ident,lifecycle_db),
          "requiresManualReconciliation":result["state"]=="UNKNOWN","exchangeWrites":False}
 return {"intentId":ident,"observedFill":None,"lifecycle":timeline(ident,lifecycle_db),
         "requiresManualReconciliation":True,"exchangeWrites":False}
