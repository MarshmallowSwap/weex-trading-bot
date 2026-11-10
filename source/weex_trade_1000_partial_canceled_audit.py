"""Offline final audit for canceled, partially-filled orders (no network).
Quantity, fill arithmetic and fees are attested separately from parent
cumQuote; mismatching parent quote is explicitly UNRESOLVED.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'weex_trade_1000_five_order_status_latest.json').read_text())
trades=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text())['trades']
ck=json.loads((ROOT/'weex_trade_1000_economics_checkpoint.json').read_text())['orders']
group=defaultdict(list)
for x in trades:group[str(x['orderId'])].append(x)
out=[]
for o in rows:
 oid=o['orderId'];fills=group[oid]
 qty=sum((D(str(f['qty'])) for f in fills),D(0))
 quote=sum((D(str(f['quoteQty'])) for f in fills),D(0))
 fee=sum((D(str(f['commission'])) for f in fills),D(0))
 parent=D(str(o['cumQuote']))
 arithmetic=all(abs(D(str(f['qty']))*D(str(f['price']))-D(str(f['quoteQty'])))<=D('0.00000001') for f in fills)
 identities=all(str(f['orderId'])==oid and f['symbol']==o['symbol'] and f['commissionAsset']=='USDT' for f in fills)
 unique=len({str(f['id']) for f in fills})==len(fills)
 partial=o['status']=='CANCELED' and qty==D(o['executedQty']) and qty<D(o['origQty']) and qty>0
 qualified=arithmetic and identities and unique and partial and ck[oid]['verified'] is False
 out.append({'orderId':oid,'symbol':o['symbol'],'status':o['status'],'partialFillQuantityVerified':qualified,
   'executedQty':str(qty),'originalQty':o['origQty'],'fillCount':len(fills),
   'fillNotionalUSDT':str(quote),'feesUSDT':str(fee),
   'orderCumQuoteUSDT':str(parent),'cumQuoteMinusFillNotionalUSDT':str(parent-quote),
   'parentQuoteMatches':parent==quote,'economicsDiscrepancyUnresolved':parent!=quote})
report={'scope':'1000_TRADE_SNAPSHOT_EXACTLY_FIVE_PARTIALLY_CANCELED_ORDERS',
 'completeFilledOrdersCertified':sum(x.get('verified') is True for x in ck.values()),
 'canceledPartiallyFilledOrders':len(out),
 'canceledPartialQuantitiesVerified':sum(x['partialFillQuantityVerified'] for x in out),
 'parentCumQuoteDiscrepancies':sum(x['economicsDiscrepancyUnresolved'] for x in out),
 'partialFillNotionalUSDT':str(sum((D(x['fillNotionalUSDT']) for x in out),D(0))),
 'partialFillFeesUSDT':str(sum((D(x['feesUSDT']) for x in out),D(0))),
 'allOrderQuantitiesVerified':len(ck)==137 and sum(x.get('verified') is True for x in ck.values())==132 and all(x['partialFillQuantityVerified'] for x in out),
 'fullEconomicCertification':False,'fullHistoricalCoverage':False,'liveGateOverride':False,'exchangeWrites':0,'details':out}
target=ROOT/'weex_trade_1000_partial_canceled_audit.json'
tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));os.replace(tmp,target)
print(json.dumps({k:v for k,v in report.items() if k!='details'}))
