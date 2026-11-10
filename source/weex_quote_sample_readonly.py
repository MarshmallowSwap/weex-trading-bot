"""Small bounded authenticated WEEX quote/fill sample, read-only.

This does not assert comprehensive economic reconciliation or live GO.
It handles missing/unknown data as unresolved and writes no exchange orders.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from weex_order_pagination import history
from weex_quote_semantics_readonly_probe import check
ROOT=Path(__file__).resolve().parent
def run(limit=6):
    rows=history(max_pages=5)
    if rows.get('completeWithinRequestedBounds') is not True:
        raise ValueError('ORDER_HISTORY_NOT_COMPLETE_WITHIN_BOUNDS')
    candidates=[]
    for x in rows['orders']:
        if x.get('status')=='FILLED' and x.get('symbol') and x.get('orderId'):
            key=(str(x['orderId']),x['symbol'])
            if key not in candidates:candidates.append(key)
        if len(candidates)==limit:break
    result=[]
    for oid,symbol in candidates:
        try:
            order=query('/capi/v3/order?orderId='+oid)
            fills=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
            verdict=check(order,fills)
            result.append({'symbol':symbol,'status':verdict.get('state'),'fillCount':verdict.get('fillCount'),
                           'orderIdSuffix':oid[-6:]})
        except Exception as e:
            result.append({'symbol':symbol,'status':'READ_FAILED','errorClass':type(e).__name__,
                           'orderIdSuffix':oid[-6:]})
    accepted={'DIRECT_QUOTE_MATCH','WEEX_LAST_PRICE_TIMES_QTY_CORROBORATED'}
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'scope':'BOUNDED_RECENT_FILLED_ORDERS',
            'sampleSize':len(result),'verifiedCount':sum(x['status'] in accepted for x in result),
            'results':result,'fullHistoricalCoverage':False,'exchangeWrites':False,
            'liveGoCertified':False}
    target=ROOT/'weex_quote_sample_readonly_latest.json'
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(temp,target)
    return report
if __name__=='__main__':
    r=run();print(json.dumps(r,ensure_ascii=False))
