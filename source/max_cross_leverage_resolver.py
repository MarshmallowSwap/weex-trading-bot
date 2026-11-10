"""Pure leverage selection policy. Never sends orders or changes exchange settings."""
from decimal import Decimal,InvalidOperation
def positive(v):
 try:
  d=Decimal(str(v))
  return d if d.is_finite() and d>0 else None
 except (TypeError,InvalidOperation,ValueError):return None
def choose(*,symbol,account_mode,exchange_settable_max,configured_cross_leverage,config):
 risk=config.get("risk",{})
 if risk.get("marginModePreference")!="cross" or risk.get("leveragePreference")!="maximum_exchange_settable_per_symbol_cross":
  return {"approved":False,"reason":"POLICY_MISMATCH"}
 if account_mode not in ("CROSSED","CROSS"):
  return {"approved":False,"reason":"NOT_CROSS_MODE"}
 maximum=positive(exchange_settable_max);current=positive(configured_cross_leverage)
 if maximum is None or current is None:return {"approved":False,"reason":"UNVERIFIED_ACCOUNT_MAX"}
 if maximum<current:return {"approved":False,"reason":"INCONSISTENT_LEVERAGE_LIMIT"}
 return {"approved":True,"symbol":symbol,"requestedLeverage":str(maximum),
         "needsLeverageChange":maximum!=current,
         "exchangeChangePerformed":False,"orderSubmitted":False}
