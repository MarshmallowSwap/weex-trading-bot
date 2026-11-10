"""WEEX strict fill-derived notional validator.

No exchange writes. cumQuote and avgPrice are diagnostic only; fee and fill
quoteQty never inferred from rounded parent-order prices. This is NOT a GO gate.
"""
from decimal import Decimal as D, InvalidOperation

TOLERANCE=D('0.00000001')
def verify(order,fills):
    deny=lambda reason: {'verified':False,'reason':reason,'liveGoCertified':False}
    if not isinstance(order,dict) or not isinstance(fills,list) or not 0<len(fills)<100:
        return deny('MISSING_OR_PAGINATED_FILLS')
    if order.get('status')!='FILLED' or not order.get('orderId'):
        return deny('ORDER_NOT_FINAL_OR_MISSING_ID')
    keys=('symbol','side','positionSide')
    if any(not order.get(k) for k in keys):return deny('ORDER_IDENTITY_INCOMPLETE')
    if len({str(f.get('id')) for f in fills})!=len(fills) or any(not f.get('id') for f in fills):
        return deny('NONUNIQUE_FILL_IDS')
    if any(str(f.get('orderId'))!=str(order['orderId']) or any(f.get(k)!=order[k] for k in keys)
           for f in fills):return deny('FILL_NOT_BOUND_TO_ORDER')
    try:
        executed=D(str(order['executedQty']))
        if not executed.is_finite() or executed<=0:return deny('INVALID_EXECUTED_QTY')
        qty=D(0);quote=D(0);fees=D(0);max_residual=D(0)
        for f in fills:
            q=D(str(f['qty']));p=D(str(f['price']));v=D(str(f['quoteQty']))
            fee=D(str(f['commission']))
            if not all(x.is_finite() for x in (q,p,v,fee)) or min(q,p,v)<=0 or fee<0:
                return deny('INVALID_FILL_VALUE')
            if f.get('commissionAsset')!='USDT':return deny('UNSUPPORTED_FEE_ASSET')
            residual=abs(q*p-v)
            if residual>TOLERANCE:return deny('FILL_PRICE_QUOTE_MISMATCH')
            max_residual=max(max_residual,residual)
            qty+=q;quote+=v;fees+=fee
        if qty!=executed:return deny('EXECUTED_QTY_DIFFERENT_FROM_FILL_SUM')
        cum=D(str(order.get('cumQuote')))
        avg=D(str(order.get('avgPrice')))
        if not all(x.is_finite() and x>=0 for x in (cum,avg)):
            return deny('INVALID_ORDER_QUOTE_OR_AVG')
    except (InvalidOperation,ValueError,TypeError,KeyError,ArithmeticError):
        return deny('MALFORMED_ECONOMIC_FIELDS')
    return {'verified':True,'reason':'FILL_DERIVED_ECONOMICS_VERIFIED',
            'symbol':order['symbol'],'fillCount':len(fills),
            'quantity':str(qty),'executedFillNotionalUSDT':str(quote),
            'executionFeeUSDT':str(fees),'maximumFillArithmeticResidual':str(max_residual),
            'orderCumQuoteUSDT':str(cum),'parentOrderQuoteDifferenceUSDT':str(cum-quote),
            'parentCumQuoteEqualFillSum':cum==quote,
            'parentCumQuoteEqualReportedAvgTimesQty':cum==avg*qty,
            'fullHistoricalCoverage':False,'liveGoCertified':False}
