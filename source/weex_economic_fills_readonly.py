"""Read-only bounded economic proof from authenticated WEEX trade fills.

Proves ONLY the orders fully observed in the latest 100 trade rows.
Never infers complete account history or authorizes live trading.
"""
from collections import defaultdict
from decimal import Decimal,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
import json,os
from monitor import query
from weex_order_pagination import history
from weex_quote_semantics_readonly_probe import check as quote_check

ROOT=Path(__file__).resolve().parent

def audit(orders,trades):
    if not isinstance(orders,list) or not isinstance(trades,list):
        raise ValueError('INVALID_EXCHANGE_RESPONSE')
    byid={str(o['orderId']):o for o in orders if isinstance(o,dict) and o.get('orderId')}
    groups=defaultdict(list)
    for f in trades:
        if not isinstance(f,dict) or not f.get('orderId'):
            raise ValueError('INVALID_FILL_IDENTITY')
        groups[str(f['orderId'])].append(f)
    results=[]
    for oid,fills in sorted(groups.items()):
        order=byid.get(oid)
        if not order:
            results.append({'orderId':oid,'state':'ORDER_NOT_IN_HISTORY'})
            continue
        try:
            qty=sum((Decimal(str(f['qty'])) for f in fills),Decimal(0))
            expected=Decimal(str(order['executedQty']))
            if not qty.is_finite() or qty<=0 or not expected.is_finite() or qty!=expected:
                state='INCOMPLETE_ORDER_FILLS'
            else:
                state=quote_check(order,fills)['state']
        except (KeyError,InvalidOperation,ValueError,TypeError):
            state='MALFORMED_ECONOMICS'
        results.append({'orderId':oid,'state':state,'fills':len(fills)})
    proven={'DIRECT_QUOTE_MATCH','WEEX_LAST_PRICE_TIMES_QTY_CORROBORATED'}
    verified=sum(x['state'] in proven for x in results)
    return {'checkedAt':datetime.now(timezone.utc).isoformat(),
            'fillRows':len(trades),'distinctOrderIds':len(groups),
            'ordersWithEconomicEvidence':verified,
            'unverifiedOrders':[x for x in results if x['state'] not in proven],
            'allBoundedOrderEconomicsVerified':len(results)>0 and verified==len(results),
            'allAccountHistoryCertified':False,'liveCrashCertified':False,
            'liveGoCertified':False,'exchangeWrites':0}

def run():
    import live_control
    if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('LIVE_NOT_STOPPED')
    fills=query('/capi/v3/userTrades?limit=100')
    h=history(max_pages=5)
    if not isinstance(fills,list) or not h.get('completeWithinRequestedBounds'):
        raise ValueError('BOUNDED_READ_INCOMPLETE')
    orders=h['orders']; known={str(o['orderId']) for o in orders if o.get('orderId')}
    missing={str(f['orderId']) for f in fills if f.get('orderId')} - known
    for oid in sorted(missing):
        o=query('/capi/v3/order?orderId='+oid)
        if not isinstance(o,dict) or str(o.get('orderId'))!=oid:
            raise ValueError('EXACT_ORDER_LOOKUP_FAILED')
        orders.append(o)
    out=audit(orders,fills)
    target=ROOT/'weex_economic_fills_readonly_latest.json';tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,indent=2),encoding='utf-8');os.replace(tmp,target)
    return out

if __name__=='__main__':
    r=run()
    print(json.dumps(r,ensure_ascii=False))
