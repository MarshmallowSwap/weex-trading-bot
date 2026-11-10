"""Offline end-to-end demo plan for documented BTCSUSDT, no order submission."""
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
from weex_demo_firewall import authorize,BASE,DEMO_SYMBOLS
root=Path(__file__).resolve().parent
def plan(symbol,side,qty,client_id,price,tp):
 if symbol not in DEMO_SYMBOLS:return {"accepted":False,"reason":"UNKNOWN_DEMO_CONTRACT"}
 if side not in ("LONG","SHORT"):return {"accepted":False,"reason":"INVALID_SIDE"}
 q=Decimal(str(qty));p=Decimal(str(price));t=Decimal(str(tp))
 if q<=0 or p<=0 or t<=0:return {"accepted":False,"reason":"INVALID_VALUES"}
 if (side=="LONG" and t<=p) or (side=="SHORT" and t>=p):return {"accepted":False,"reason":"TP_WRONG_SIDE"}
 endpoint=BASE+"/capi/v3/sim/order"
 if not authorize("POST",endpoint,symbol,allow_demo_writes=True)["allowed"]:
  return {"accepted":False,"reason":"DEMO_FIREWALL_DENIED"}
 return {"accepted":True,"environment":"DEMO_PLAN_ONLY","symbol":symbol,"side":"BUY" if side=="LONG" else "SELL",
  "positionSide":side,"type":"LIMIT","timeInForce":"GTC","quantity":str(q),
  "price":str(p),"tpTriggerPrice":str(t),"newClientOrderId":client_id,"submitted":False}
if __name__=="__main__":
 r=plan("BTCSUSDT","LONG","0.001","demo-plan-001","69000","70000")
 p=root/"demo_order_plan_latest.json";p.write_text(json.dumps({"at":datetime.now(timezone.utc).isoformat(),"candidate":r},indent=2),encoding="utf-8")
 print("demo plan",r["accepted"],"submitted",r.get("submitted"))
