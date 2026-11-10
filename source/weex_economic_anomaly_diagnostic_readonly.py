"""Targeted anomaly diagnostics: authenticated GETs only, no writes."""
import json
from pathlib import Path
from decimal import Decimal as D
from monitor import query

R=Path(__file__).resolve().parent
items=json.loads((R/'weex_economic_fills_readonly_latest.json').read_text())['unverifiedOrders']
for item in items:
    oid=item['orderId']
    o=query('/capi/v3/order?orderId='+oid)
    fills=query('/capi/v3/userTrades?orderId='+oid+'&limit=100')
    out={'reason':item['state'],'symbol':o.get('symbol'),
         'type':o.get('type'),'orderStatus':o.get('status'),
         'orderQty':o.get('executedQty'),'orderCumQuote':o.get('cumQuote'),
         'average':o.get('avgPrice'),'fillCount':len(fills),
         'fillQty':str(sum((D(str(f.get('qty','0'))) for f in fills),D(0))),
         'fillQuote':str(sum((D(str(f.get('quoteQty','0'))) for f in fills),D(0))),
         'commissionAssets':sorted(set(str(f.get('commissionAsset')) for f in fills)),
         'fillPrices':sorted(set(str(f.get('price')) for f in fills)),
         'orderSide':o.get('side'),
         'fillSides':sorted(set(str(f.get('side')) for f in fills))}
    print(json.dumps(out,ensure_ascii=False))
