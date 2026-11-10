"""Conservative read-only WEEX order reconciliation. No writes to exchange."""
import json
from pathlib import Path
from monitor import query
ROOT=Path(__file__).resolve().parent
def fetch():
 paths=("/capi/v3/openOrders?limit=100&page=0","/capi/v3/order/history?limit=100&page=0")
 result={}
 for path in paths:
  try:
   records=query(path)
   if not isinstance(records,list):raise ValueError("Unexpected response shape")
   result[path]={"status":"OK","count":len(records),"records":records}
  except Exception as exc:result[path]={"status":"ERROR","error":type(exc).__name__}
 return result
def reconcile(intent,orders):
 """Require explicit exchange order ID binding, never infer intent from symbol alone."""
 order_id=intent.get("exchangeOrderId")
 if not order_id:return {"state":"UNBOUND_INTENT","executable":False}
 matches=[o for o in orders if str(o.get("orderId"))==str(order_id)]
 if len(matches)!=1:return {"state":"UNKNOWN_RECONCILIATION_REQUIRED","executable":False}
 order=matches[0]
 state=str(order.get("status","")).upper()
 if state in ("FILLED","FULLY_FILLED"):result="FILLED"
 elif state in ("PARTIALLY_FILLED","PARTIAL_FILLED"):result="PARTIAL"
 elif state in ("CANCELED","CANCELLED"):result="CANCELLED"
 elif state in ("NEW","OPEN"):result="OPEN"
 else:result="UNKNOWN_RECONCILIATION_REQUIRED"
 return {"state":result,"executable":False,"exchangeOrderId":str(order_id)}
if __name__=="__main__":
 response=fetch()
 print({path:{"status":v["status"],"count":v.get("count")} for path,v in response.items()})
