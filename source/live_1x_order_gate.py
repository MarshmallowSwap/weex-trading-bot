"""LIVE 1x pilot: pure fail-closed gate. NO order or leverage API writes."""
from decimal import Decimal, InvalidOperation
def pos(x):
 try:
  d=Decimal(str(x))
  return d if d.is_finite() and d>0 else None
 except (InvalidOperation,ValueError,TypeError):return None
def assess(*,symbol,positions,open_orders,account_mode,configured_leverage,
           min_notional,requested_notional="5",close_procedure_verified=False,
           reduce_only_verified=False,client_order_binding_verified=False,
           execution_enabled=False):
 reasons=[]
 if not symbol or not symbol.endswith("USDT"):reasons.append("INVALID_SYMBOL")
 if not isinstance(positions,list) or not isinstance(open_orders,list):
  reasons.append("UNAVAILABLE_ACCOUNT_SNAPSHOT")
 else:
  if any(x.get("symbol")==symbol for x in positions+open_orders):reasons.append("SYMBOL_ALREADY_IN_USE")
 if account_mode not in ("CROSS","CROSSED"):reasons.append("NOT_CROSS")
 if pos(configured_leverage)!=Decimal(1):reasons.append("NOT_1X")
 n=pos(requested_notional);mn=pos(min_notional)
 if n is None or n>Decimal(5):reasons.append("NOTIONAL_OVER_5USDT")
 if mn is None or n is None or n<mn:reasons.append("MIN_ORDER_NOT_VERIFIED")
 if not close_procedure_verified:reasons.append("CLOSE_NOT_VERIFIED")
 if not reduce_only_verified:reasons.append("REDUCE_ONLY_NOT_VERIFIED")
 if not client_order_binding_verified:reasons.append("ORDER_BINDING_NOT_VERIFIED")
 if execution_enabled:reasons.append("PREFLIGHT_REQUIRES_EXECUTION_OFF")
 return {"preflightPassed":not reasons,"blockers":reasons,"ordersSubmitted":False}
