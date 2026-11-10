"""WEEX V3 exit payload validation and quantity rounding. PURE: no network calls."""
from decimal import Decimal,ROUND_FLOOR
import re
D=lambda x:Decimal(str(x))
ID=re.compile(r"^[.A-Z:/a-z0-9_-]{1,36}$")
def make_tp_sl(*,symbol,position_side,quantity,step,tick,trigger,client_algo_id,plan_type="TAKE_PROFIT",position_mode="HEDGE",source="MARK_PRICE"):
 if not ID.fullmatch(client_algo_id):raise ValueError("Invalid clientAlgoId")
 if position_side not in ("LONG","SHORT"):raise ValueError("Invalid position side")
 if plan_type not in ("TAKE_PROFIT","STOP_LOSS"):raise ValueError("Invalid plan type")
 if source not in ("MARK_PRICE","CONTRACT_PRICE"):raise ValueError("Invalid trigger source")
 if position_mode not in ("HEDGE","ONE_WAY"):raise ValueError("Unknown position mode")
 if position_mode=="ONE_WAY":raise ValueError("One-way compatibility not yet certified")
 q,unit,p,t=D(quantity),D(step),D(trigger),D(tick)
 if not all(x.is_finite() and x>0 for x in (q,unit,p,t)):raise ValueError("Invalid quantity/price")
 q=(q/unit).to_integral_value(rounding=ROUND_FLOOR)*unit
 if q<=0:raise ValueError("Remaining quantity smaller than lot")
 if p%t!=0:raise ValueError("Trigger price must match tick")
 return {"symbol":symbol,"clientAlgoId":client_algo_id,"planType":plan_type,
         "triggerPrice":str(p),"executePrice":"0","quantity":str(q),
         "positionSide":position_side,"triggerPriceType":source,"reduceOnly":True}
