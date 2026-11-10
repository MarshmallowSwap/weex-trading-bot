"""Fail-closed independent read-only evidence for an isolated pilot exit.

Caller supplies authenticated observations. This never authorizes an order.
"""
from decimal import Decimal, InvalidOperation

def verify_close(*, client_id, side, quantity, orders, fills, positions):
    deny=lambda reason: {'state':'UNVERIFIED','reason':reason,'canSend':False,
                         'canRetry':False,'closeCertifiedForLive':False}
    if side not in ('LONG','SHORT') or not client_id:
        return deny('INVALID_PILOT_IDENTITY')
    if not all(isinstance(x,list) for x in (orders,fills,positions)):
        return deny('INCOMPLETE_SNAPSHOT')
    matches=[o for o in orders if isinstance(o,dict) and
             str(o.get('clientOrderId') or '')==client_id]
    if len(matches)!=1:return deny('MISSING_OR_AMBIGUOUS_EXIT')
    o=matches[0]
    expected='SELL' if side=='LONG' else 'BUY'
    try:
        qty=Decimal(str(quantity))
        executed=Decimal(str(o['executedQty']))
        original=Decimal(str(o['origQty']))
        if (not qty.is_finite() or qty<=0 or not executed.is_finite()
            or original!=qty or executed!=qty
            or o.get('symbol')!='ETHUSDT' or o.get('positionSide')!=side
            or o.get('side')!=expected or o.get('reduceOnly') is not True
            or str(o.get('status')).upper()!='FILLED' or not o.get('orderId')):
            return deny('CLOSE_ORDER_NOT_EXACT')
        selected=[f for f in fills if isinstance(f,dict) and
                  str(f.get('orderId'))==str(o['orderId'])]
        if not selected:return deny('FILLS_NOT_AVAILABLE')
        fill_ids=[str(f.get('id') or '') for f in selected]
        if any(not i for i in fill_ids) or len(fill_ids)!=len(set(fill_ids)):
            return deny('DUPLICATE_OR_MISSING_FILL_ID')
        total=Decimal('0')
        for f in selected:
            if (f.get('symbol')!='ETHUSDT' or f.get('positionSide')!=side
                or f.get('side')!=expected):
                return deny('FILL_IDENTITY_MISMATCH')
            q=Decimal(str(f['qty']))
            if not q.is_finite() or q<=0:return deny('INVALID_FILL')
            total+=q
        if total!=qty:return deny('INCOMPLETE_FILLS')
        for p in positions:
            if not isinstance(p,dict):return deny('INVALID_POSITION_OBSERVATION')
            if p.get('symbol')=='ETHUSDT' and p.get('positionSide')==side:
                remaining=Decimal(str(p.get('positionAmt',p.get('size'))))
                if not remaining.is_finite() or remaining!=0:
                    return deny('POSITION_STILL_OPEN')
    except (InvalidOperation,KeyError,TypeError,ValueError):
        return deny('MALFORMED_EXCHANGE_DATA')
    # Snapshot from a caller is not independently attested or necessarily
    # atomic; proof remains informational and cannot certify live operation.
    return {'state':'CONSISTENT_OBSERVATIONS_UNATTESTED',
            'reason':'NONATOMIC_SNAPSHOT_REQUIRES_INDEPENDENT_CONFIRMATION',
            'canSend':False,'canRetry':False,'closeCertifiedForLive':False}
