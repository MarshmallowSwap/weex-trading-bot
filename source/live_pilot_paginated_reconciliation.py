"""Bounded authenticated WEEX trade/history reconciliation; GET only."""
import json,os
from pathlib import Path
from weex_pilot_binding_readonly import inspect as inspect_pilot
from datetime import datetime,timezone
from monitor import query
from weex_order_pagination import history
R=Path(__file__).resolve().parent
trades=query("/capi/v3/userTrades?limit=100")
hist=history(max_pages=5)
if not isinstance(trades,list):raise ValueError("invalid trades response")
orders=hist["orders"]
byid={str(o["orderId"]):o for o in orders if isinstance(o,dict) and o.get("orderId")}
# Resolve known exchange order IDs by authenticated GET, never by guesswork.
# A failed or inconsistent lookup remains unresolved and never authorizes trading.
unresolved_ids=sorted({str(t.get("orderId")) for t in trades
                       if t.get("orderId") and str(t["orderId"]) not in byid})
recovered={}
lookup_failures=[]
for oid in unresolved_ids:
 try:
  detail=query("/capi/v3/order?orderId="+oid)
  if (not isinstance(detail,dict) or str(detail.get("orderId"))!=oid
      or not detail.get("clientOrderId") or not detail.get("symbol")):
   raise ValueError("ORDER_DETAIL_MISMATCH")
  if any(str(t.get("orderId"))==oid and t.get("symbol")!=detail["symbol"] for t in trades):
   raise ValueError("ORDER_SYMBOL_MISMATCH")
  recovered[oid]=detail
 except Exception:
  lookup_failures.append(oid)
byid.update(recovered)
matched=[t for t in trades if str(t.get("orderId")) in byid]
missing=[t for t in trades if str(t.get("orderId")) not in byid]
# Use a known local SDK journal only if it already exists, or an explicit path.
# Historical matches alone never establish pilot ownership or live approval.
pilot_db=os.environ.get('WEEX_PILOT_JOURNAL_READONLY')
if not pilot_db:
 # The isolated pilot journal takes priority over the separate SDK dry-run log.
 for candidate in (R/'weex_isolated_pilot.sqlite3',R/'live_sdk_intent_journal.sqlite3'):
  if candidate.is_file():
   pilot_db=str(candidate)
   break
pilot_audit=inspect_pilot(pilot_db, list(byid.values())) if pilot_db else {
 'state':'PILOT_JOURNAL_NOT_CONFIGURED','pilots':0,'stages':[],
 'canSend':False,'canRetry':False,'exchangeWrites':0}
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"tradeCount":len(trades),
"orderCount":len(orders),"matched":len(matched),"unmatched":len(missing),
"unmatchedOrders":[{"orderId":str(t.get("orderId")),"symbol":t.get("symbol"),"time":t.get("time")} for t in missing],
"paginationCompleteWithinBounds":hist["completeWithinRequestedBounds"],
"directLookupRecoveredOrders":len(recovered),"directLookupFailedOrders":len(lookup_failures),
"recoveredOrderIds":sorted(recovered),"unresolvedOrderIds":lookup_failures,
"botOrderBindingsVerified":0,"pilotBindingAudit":pilot_audit,
"pilotOrderAuthorized":False,"exchangeWrites":False}
p=R/"live_pilot_paginated_reconciliation_latest.json";tmp=p.with_suffix(".tmp")
tmp.write_text(json.dumps(out,indent=2),encoding="utf-8");tmp.replace(p)
print("trades",len(trades),"history",len(orders),"matched",len(matched),"unmatched",len(missing),"pages_bounded",out["paginationCompleteWithinBounds"])
