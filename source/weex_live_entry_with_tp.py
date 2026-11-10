"""WEEX official SDK one-shot OPEN with inline TP. No background trading.
Exchange write is permitted only by an explicitly enabled, approved adapter.
"""
from decimal import Decimal
from official_weex_live_sdk_adapter import LiveSdkReadOnly
def build_order(*,symbol,side,quantity,price,tp_price,client_order_id):
 if symbol!="ETHUSDT":raise ValueError("PILOT_ONLY_ETHUSDT")
 if side not in ("LONG","SHORT"):raise ValueError("INVALID_DIRECTION")
 q,p,tp=(Decimal(str(x)) for x in (quantity,price,tp_price))
 if not all(x.is_finite() and x>0 for x in (q,p,tp)):raise ValueError("INVALID_PRICE_OR_SIZE")
 if q*p>Decimal("5"):raise ValueError("MAX_NOTIONAL_5_USDT")
 if (side=="LONG" and tp<=p) or (side=="SHORT" and tp>=p):raise ValueError("TP_NOT_PROFITABLE")
 if not (client_order_id.startswith("wxpilot_") and len(client_order_id)<=36):raise ValueError("UNSAFE_CLIENT_ORDER_ID")
 return {"symbol":symbol,"side":"BUY" if side=="LONG" else "SELL",
         "positionSide":side,"type":"MARKET","quantity":str(q),"newClientOrderId":client_order_id,
         "tpTriggerPrice":str(tp),"TpWorkingType":"MARK_PRICE"}
def send_order(order,*,client=None,approval=None):
 if not isinstance(order,dict) or not order.get("tpTriggerPrice"):raise ValueError("INLINE_TP_REQUIRED")
 adapter=LiveSdkReadOnly(client,write_approval=approval)
 return adapter.execute("post_capi_v3_order",order)
