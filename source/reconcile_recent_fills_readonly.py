"""Read-only reconciliation of missing trade rows by exact WEEX order ID."""
import json
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from monitor import query
from weex_quote_semantics_readonly_probe import check as exact_quote_check
R=Path(__file__).resolve().parent
src=json.loads((R/"live_pilot_paginated_reconciliation_latest.json").read_text(encoding="utf-8"))
acct=json.loads((R/"weex_account_observation_latest.json").read_text(encoding="utf-8"))
groups={}
for x in src.get("unmatchedOrders",[]):
    key=(str(x.get("orderId") or ""),str(x.get("symbol") or ""))
    if all(key):groups[key]=groups.get(key,0)+1
items=[]
for (oid,sym),expected in sorted(groups.items()):
    out={"orderId":oid,"symbol":sym,"expectedMissingRows":expected}
    try:
        order=query(f"/capi/v3/order?orderId={oid}")
        fills=query(f"/capi/v3/userTrades?symbol={sym}&orderId={oid}&limit=100")
        if not isinstance(order,dict) or not isinstance(fills,list):raise ValueError("BAD_RESPONSE")
        qty=sum((D(str(x["qty"])) for x in fills),D(0))
        quote=sum((D(str(x["quoteQty"])) for x in fills),D(0))
        fees=sum((D(str(x.get("commission","0"))) for x in fills if x.get("commissionAsset")=="USDT"),D(0))
        assets=sorted({str(x.get("commissionAsset")) for x in fills})
        execq=D(str(order.get("executedQty","0")));cum=D(str(order.get("cumQuote","0")))
        unique=len({str(x.get("id")) for x in fills})==len(fills)
        same=all(str(x.get("orderId"))==oid for x in fills)
        identity=str(order.get("orderId"))==oid and order.get("symbol")==sym
        qtyok=qty==execq
        countok=len(fills)==expected and len(fills)<100
        quote_delta=cum-quote
        quote_proof=exact_quote_check(order,fills)
        out.update({"status":"ORDER_AND_FILL_ID_VERIFIED" if all((identity,same,unique,qtyok,countok)) else "UNRESOLVED",
          "orderStatus":order.get("status"),"type":order.get("type"),"side":order.get("side"),
          "positionSide":order.get("positionSide"),"clientOrderId":order.get("clientOrderId"),
          "fillCount":len(fills),"quantity":str(qty),"executedQty":str(execq),
          "fillQuoteSum":str(quote),"orderCumQuote":str(cum),"quoteDelta":str(quote_delta),
          "feeSumUSDT":str(fees),"commissionAssets":assets,
          "quoteSemantics":quote_proof,"economicNotionalSource":"EXACT_EXECUTED_FILLS",
          "checks":{"orderIdentity":identity,"sameOrderIdAllFills":same,"uniqueFillIds":unique,
          "quantityMatches":qtyok,"missingRowCountMatches":countok,
          "cumQuoteEqualsFillQuote":quote==cum,
          "cumQuoteEqualsFillQuotePlusUsdtFee":abs(cum-quote-fees)<=max(D("0.00000001"),abs(cum)*D("0.000001"))}})
    except Exception as e:out.update({"status":"READ_FAILED","error":type(e).__name__})
    items.append(out)
# Zero missing rows is a successful *identity* reconciliation, not a
# certificate of fill economics. Do not require a fabricated missing order.
none_missing=(src.get('unmatched')==0 and src.get('matched')==src.get('tradeCount')
              and isinstance(src.get('tradeCount'),int) and src['tradeCount']>0
              and src.get('paginationCompleteWithinBounds') is True)
bindings=(none_missing if not groups else
          all(x.get("status")=="ORDER_AND_FILL_ID_VERIFIED" for x in items) and bool(items))
quote_certified=bool(items) and bindings and all(x["quoteSemantics"].get("state") in ("WEEX_LAST_PRICE_TIMES_QTY_CORROBORATED","DIRECT_QUOTE_MATCH") for x in items)
quote_direct=quote_certified and all(x["quoteSemantics"].get("state")=="DIRECT_QUOTE_MATCH" for x in items)
res={"checkedAt":datetime.now(timezone.utc).isoformat(),"sourceCheckedAt":src.get("checkedAt"),
 "accountObservedAt":acct.get("observedAt"),"sourceTradeRows":src.get("tradeCount"),
 "sourceMatchedToHistory":src.get("matched"),"sourceMissingRows":src.get("unmatched"),
 "distinctMissingOrders":len(groups),"items":items,
 "recentMissingOrderFillIdentityResolved":bindings,
 "financialQuoteReconciliation":("MATCHED" if quote_direct else
     "FILL_NOTIONAL_VERIFIED_ALTERNATE_WEEX_CUMQUOTE" if quote_certified else "INCOMPLETE"),
 "economicNotionalCertifiedFromFills":quote_certified,
 "economicsFundingIncluded":False,
 "fullHistoricalCoverage":False,"positionOwnershipInferred":False,
 "exchangeWrites":False,"telegramMessagesSent":False}
p=R/"live_recent_fill_reconciliation_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(res,indent=2),encoding="utf-8");t.replace(p)
print(json.dumps({"recentMissingOrderFillIdentityResolved":bindings,
 "financialQuoteReconciliation":res["financialQuoteReconciliation"],"items":items,
 "exchangeWrites":False},ensure_ascii=False))
