"""Read-only bounded forensic probe of two known mismatched WEEX orders."""
import json
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime,timezone
from weex_order_pagination import history
from monitor import query
from weex_quote_semantics_readonly_probe import check
ROOT=Path(__file__).resolve().parent
TARGETS={'TRUTHUSDT':'062410','UAIUSDT':'707338'}
def run():
    h=history(max_pages=5)
    if h.get('completeWithinRequestedBounds') is not True:
        raise RuntimeError('BOUNDED_HISTORY_INCOMPLETE')
    results=[]
    for symbol,suffix in TARGETS.items():
        matches=[o for o in h['orders'] if o.get('symbol')==symbol and str(o.get('orderId','')).endswith(suffix)]
        if len(matches)!=1:
            results.append({'symbol':symbol,'status':'NOT_UNIQUE_IN_BOUNDED_HISTORY','count':len(matches)})
            continue
        oid=str(matches[0]['orderId'])
        try:
            order=query('/capi/v3/order?orderId='+oid)
            fills=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
            if not isinstance(order,dict) or not isinstance(fills,list):
                raise ValueError('BAD_ACCOUNT_DATA')
            verdict=check(order,fills)
            quantities=[]
            for f in fills:
                q=D(str(f['qty']));price=D(str(f['price']));quote=D(str(f['quoteQty']))
                quantities.append({'qty':str(q),'price':str(price),'quoteQty':str(quote),
                                   'product':str(q*price),'difference':str(quote-q*price),
                                   'commissionAsset':f.get('commissionAsset')})
            results.append({'symbol':symbol,'status':verdict['state'],
                            'orderStatus':order.get('status'),'qty':order.get('executedQty'),
                            'cumQuote':order.get('cumQuote'),'avgPrice':order.get('avgPrice'),
                            'fills':quantities,'fillCount':len(fills),
                            'verdict':verdict})
        except Exception as exc:
            results.append({'symbol':symbol,'status':'READ_FAILED','errorClass':type(exc).__name__})
    report={'at':datetime.now(timezone.utc).isoformat(),'results':results,'exchangeWrites':False,
            'sampleNotCertification':True}
    target=ROOT/'weex_economic_forensics_latest.json';target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':run()
