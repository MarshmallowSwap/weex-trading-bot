"""Authenticated bounded WEEX quote anomalies: factual evidence only.

This report does not reconcile divergent accounting or certify LIVE release.
Only read-only GET endpoints. Does not send orders or update gate checks.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from monitor import query
import live_control
ROOT=Path(__file__).resolve().parent
IDS=('812888475840807114','813057432287707338','813057432468062410')

def analyze(order, fills):
    try:
        qty=Decimal(str(order['executedQty']))
        fill_qty=sum((Decimal(str(f['qty'])) for f in fills),Decimal(0))
        fill_notional=sum((Decimal(str(f['quoteQty'])) for f in fills),Decimal(0))
        cum=Decimal(str(order['cumQuote']))
        avg=Decimal(str(order['avgPrice']))
        calculated=sum((Decimal(str(f['qty']))*Decimal(str(f['price'])) for f in fills),Decimal(0))
        discrepancy=cum-fill_notional
        status=str(order['status'])
        if fill_qty!=qty or not fills:
            reason='MISSING_OR_INCOMPLETE_FILLS'
        elif status!='FILLED':
            reason='ORDER_STATUS_CONFLICT_WITH_EXECUTED_QUANTITY'
        elif any(abs(Decimal(str(f['quoteQty']))-
                     Decimal(str(f['qty']))*Decimal(str(f['price'])))>Decimal('.00000001')
                 for f in fills):
            reason='FILL_PRICE_QUOTE_NOT_EXACT'
        elif discrepancy:
            reason='ORDER_CUMQUOTE_DIFFERS_FROM_FILLS'
        else:reason='DIRECT_ECONOMICS_MATCH'
        return {'orderId':str(order['orderId']),'symbol':order['symbol'],
                'status':status,'executedQty':str(qty),'fillQty':str(fill_qty),
                'fillCount':len(fills),'orderCumQuoteUSDT':str(cum),
                'fillNotionalUSDT':str(fill_notional),
                'fillQtyTimesPriceUSDT':str(calculated),
                'orderQtyTimesAvgUSDT':str(qty*avg),
                'cumQuoteMinusFillUSDT':str(discrepancy),
                'classification':reason,'economicCertified':reason=='DIRECT_ECONOMICS_MATCH'}
    except (ValueError,KeyError,InvalidOperation,TypeError):
        return {'orderId':str(order.get('orderId')),'classification':'INVALID_EVIDENCE',
                'economicCertified':False}
def run():
    if live_control.state(ROOT)['mode']!='STOPPED':
        raise PermissionError('LIVE_NOT_STOPPED')
    rows=[]
    for oid in IDS:
        order=query('/capi/v3/order?orderId='+oid)
        fills=query('/capi/v3/userTrades?orderId='+oid+'&limit=100')
        if (not isinstance(order,dict) or str(order.get('orderId'))!=oid
                or not isinstance(fills,list) or not fills or len(fills)>=100
                or any(str(f.get('orderId'))!=oid for f in fills)):
            raise ValueError('NON_ATTESTABLE_ORDER_'+oid)
        rows.append(analyze(order,fills))
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),
            'scope':'THREE_SPECIFIC_HISTORICAL_WEEX_ORDERS',
            'cases':rows,'allThreeReconciled':all(x['economicCertified'] for x in rows),
            'liveCrashCertified':False,'canEnableTrading':False,'exchangeWrites':0}
    path=ROOT/'weex_three_economic_exceptions_evidence_latest.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,path)
    return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
