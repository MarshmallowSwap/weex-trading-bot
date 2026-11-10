"""WEEX exit planner: calculation only, never submits/cancels orders."""
from decimal import Decimal, InvalidOperation
D=lambda x: Decimal(str(x))
def plan(position, *, break_even, profit_usdt, fee_rate, tick_size, stop_price=None, trailing_extreme=None, trailing_distance=None):
 side=str(position.get("side","")).upper()
 if side not in ("LONG","SHORT"):raise ValueError("Invalid side")
 qty=D(position["remainingBaseQty"]);be=D(break_even);target=D(profit_usdt)
 fee=D(fee_rate);tick=D(tick_size)
 if any(not x.is_finite() for x in (qty,be,target,fee,tick)) or min(qty,be,target,tick)<=0 or fee<0 or fee>=1:raise ValueError("Invalid numeric inputs")
 direction=D(1) if side=="LONG" else D(-1)
 den=qty*(direction-fee)
 if (den>0)!=(direction>0):raise ValueError("Invalid denominator")
 theoretical=be+target/den
 rounding="ROUND_CEILING" if side=="LONG" else "ROUND_FLOOR"
 tp=(theoretical/tick).to_integral_value(rounding=rounding)*tick
 if tp<=0:raise ValueError("Invalid TP")
 stop=None
 if stop_price is not None:stop=D(stop_price)
 if trailing_extreme is not None:
  if trailing_distance is None:raise ValueError("Trailing distance missing")
  candidate=D(trailing_extreme)-direction*D(trailing_distance)
  if candidate<=0:raise ValueError("Invalid trailing stop")
  stop=max(stop,candidate) if side=="LONG" and stop is not None else min(stop,candidate) if stop is not None else candidate
 if stop is not None:
  if not stop.is_finite() or stop<=0:raise ValueError("Invalid stop")
  stop=(stop/tick).to_integral_value(rounding="ROUND_FLOOR" if side=="LONG" else "ROUND_CEILING")*tick
 return {"side":side,"remainingQty":str(qty),"takeProfitPrice":str(tp),
         "stopCandidatePrice":str(stop) if stop is not None else None,
         "exitSide":"SELL" if side=="LONG" else "BUY","reduceOnly":True,
         "requiresPositionReconciliation":True,"orderSubmissionEnabled":False,
         "warning":"Calculation only; exit costs, exchange position mode and trigger semantics require verification."}
