"""WEEX position sizing for 5 USDT INITIAL MARGIN (not notional).
Calculation only, no exchange writes. Exchange metadata and real leverage required.
"""
from decimal import Decimal, ROUND_DOWN

def contract_rules(metadata):
 """Validate WEEX V3 linear-USDT metadata, including negative precision."""
 if metadata.get("quoteAsset") != "USDT" or metadata.get("marginAsset") != "USDT" or metadata.get("forwardContractFlag") is not True:
  raise ValueError("UNSUPPORTED_CONTRACT")
 precisions=[]
 for name in ("quantityPrecision", "pricePrecision"):
  value=metadata.get(name)
  if isinstance(value,bool) or not isinstance(value,int) or not -12<=value<=18:
   raise ValueError("INVALID_CONTRACT_PRECISION")
  precisions.append(value)
 step,tick=(Decimal(1).scaleb(-p) for p in precisions)
 values=[Decimal(str(metadata[k])) for k in ("minOrderSize","maxOrderSize","marketOpenLimitSize","minLeverage","maxLeverage")]
 if any(not v.is_finite() or v<=0 for v in values):raise ValueError("INVALID_CONTRACT_LIMIT")
 minimum,maximum,market_max,min_lev,max_lev=values
 if minimum>min(maximum,market_max) or min_lev>max_lev:raise ValueError("INCONSISTENT_CONTRACT_LIMIT")
 return {"quantityStep":step,"priceTick":tick,"minQuantity":minimum,
         "maxQuantity":min(maximum,market_max),"minLeverage":min_lev,"maxLeverage":max_lev}

def size_for_contract(*,metadata,margin_usdt,leverage,reference_price):
 rules=contract_rules(metadata)
 lev=Decimal(str(leverage))
 if not lev.is_finite() or not rules["minLeverage"]<=lev<=rules["maxLeverage"]:
  raise ValueError("LEVERAGE_OUTSIDE_CONTRACT_LIMITS")
 result=size_from_margin(margin_usdt=margin_usdt,leverage=leverage,
   reference_price=reference_price,quantity_step=rules["quantityStep"])
 qty=Decimal(result["quantity"])
 if qty<rules["minQuantity"]:raise ValueError("QUANTITY_BELOW_EXCHANGE_MINIMUM")
 if qty>rules["maxQuantity"]:raise ValueError("QUANTITY_ABOVE_EXCHANGE_MAXIMUM")
 result.update(quantityStep=str(rules["quantityStep"]),priceTick=str(rules["priceTick"]))
 return result
def size_from_margin(*,margin_usdt,leverage,reference_price,quantity_step,fee_reserve_usdt="0"):
 d=lambda x:Decimal(str(x))
 m,lev,price,step,fees=map(d,(margin_usdt,leverage,reference_price,quantity_step,fee_reserve_usdt))
 if not all(v.is_finite() for v in (m,lev,price,step,fees)) or min(m,lev,price,step)<=0 or fees<0 or fees>=m:
  raise ValueError("INVALID_SIZING_INPUT")
 raw=(m-fees)*lev/price
 qty=(raw/step).to_integral_value(rounding=ROUND_DOWN)*step
 if qty<=0:raise ValueError("QUANTITY_BELOW_STEP")
 notional=qty*price
 return {"quantity":format(qty,"f"),"initialMarginUSDT":format(notional/lev,"f"),
   "notionalUSDT":format(notional,"f"),"leverage":format(lev,"f"),
   "targetMarginUSDT":format(m,"f"),
   "requiresExchangeLeverageAndContractStepVerification":True}
