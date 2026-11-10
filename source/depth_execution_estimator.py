"""Read-only cost-aware execution feasibility (scenario analysis, never permits orders)."""
from decimal import Decimal
D=lambda x:Decimal(str(x))
def estimate(book,side,margin,leverage,fee_rate,contract_multiplier=None):
 if side not in ("LONG","SHORT"):raise ValueError("Invalid side")
 target=D(margin)*D(leverage)
 if target<=0 or D(fee_rate)<0:raise ValueError("Invalid parameters")
 # WEEX V3 book units have not been certified: reject conversion for live use.
 if contract_multiplier is None:
  return {"status":"UNVERIFIED_UNITS","eligibleForTrading":False,"targetNotionalUSDT":str(target)}
 levels=book["asks"] if side=="LONG" else book["bids"]
 remaining=target;spent=D(0);base=D(0)
 for price,size in levels:
  p=D(price);q=D(size)*D(contract_multiplier)
  if p<=0 or q<=0:raise ValueError("Invalid book level")
  take=min(remaining,p*q);spent+=take;base+=take/p;remaining-=take
  if remaining<=0:break
 fee=spent*D(fee_rate)
 return {"status":"SCENARIO_ONLY","eligibleForTrading":False,
         "targetNotionalUSDT":str(target),"filledNotionalUSDT":str(spent),
         "unfilledNotionalUSDT":str(remaining),"averagePrice":str(spent/base) if base else None,
         "entryFeeEstimateUSDT":str(fee),"unitMultiplierAssumed":str(contract_multiplier)}
