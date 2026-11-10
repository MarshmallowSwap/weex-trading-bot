"""GET-only audit of two precisely identified WEEX orders with strict fill value."""
import json
from datetime import datetime,timezone
from pathlib import Path
from monitor import query
from weex_order_pagination import history
from weex_fill_notional_strict import verify
ROOT=Path(__file__).resolve().parent
TARGETS=(('TRUTHUSDT','062410'),('UAIUSDT','707338'))
def run():
    h=history(max_pages=5)
    if h.get('completeWithinRequestedBounds') is not True:
        raise ValueError('HISTORY_INCOMPLETE')
    results=[]
    for symbol,suffix in TARGETS:
        rows=[x for x in h['orders'] if x.get('symbol')==symbol and str(x.get('orderId','')).endswith(suffix)]
        if len(rows)!=1:
            results.append({'symbol':symbol,'verified':False,'reason':'ORDER_NOT_UNIQUE'});continue
        oid=str(rows[0]['orderId'])
        try:
            order=query('/capi/v3/order?orderId='+oid)
            fills=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
            proof=verify(order,fills)
            results.append({'symbol':symbol,'orderIdSuffix':suffix,**proof})
        except Exception as e:
            results.append({'symbol':symbol,'verified':False,'reason':'READ_FAILED',
                            'errorClass':type(e).__name__})
    r={'checkedAt':datetime.now(timezone.utc).isoformat(),'scope':'TWO_ORDERS_ONLY',
       'results':results,'verifiedCount':sum(x.get('verified') is True for x in results),
       'fullHistoricalCoverage':False,'exchangeWrites':False,'liveGoCertified':False}
    target=ROOT/'weex_fill_notional_audit_latest.json'
    target.write_text(json.dumps(r,indent=2),encoding='utf-8')
    return r
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
