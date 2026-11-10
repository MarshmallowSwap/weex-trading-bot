"""Fail-closed exchange stop lifecycle for a *single* isolated pilot.

No orders sent. Never cancel by symbol. Matching an active stop is not consent
to cancel it; that requires an explicitly approved exact algo ID and exchange
readback, serialized with all exit mechanisms.
"""
from decimal import Decimal, InvalidOperation

ACTIVE={'NEW','UNTRIGGERED','OPEN','ACTIVE'}
TERMINAL={'CANCELED','CANCELLED','EXPIRED','FILLED'}
def positive(value):
    try:
        x=Decimal(str(value))
        return x if x.is_finite() and x>0 else None
    except (TypeError,ValueError,InvalidOperation):return None

def assess(*,positions,regular,conditional,expected_position=None,expected_stop=None):
    def deny(reason,**details):
        return {'readyToDispatchEmergency':False,'canCancel':False,
                'reason':reason,'exchangeWrites':0,**details}
    if not all(isinstance(x,list) for x in (positions,regular,conditional)):
        return deny('INCOMPLETE_ACCOUNT_OBSERVATION')
    if regular:return deny('OTHER_REGULAR_ORDERS_PRESENT')
    if not positions:
        if not conditional:return {'readyToDispatchEmergency':False,'canCancel':False,
            'reason':'ACCOUNT_FLAT_AND_NO_RESIDUAL_STOP','exchangeWrites':0,
            'flatVerified':True}
        if len(conditional)==1 and isinstance(conditional[0],dict):
            c=conditional[0]
            if expected_stop and c.get('symbol')=='ETHUSDT' and str(c.get('algoId'))==str(expected_stop.get('algoId')):
                return deny('ACCOUNT_FLAT_RESIDUAL_STOP_NEEDS_EXACT_CANCEL_READBACK',
                            orphanAlgoId=str(c['algoId']),flatVerified=True)
        return deny('ACCOUNT_FLAT_OTHER_CONDITIONAL_ORDERS')
    if len(positions)!=1 or not isinstance(expected_position,dict):
        return deny('POSITION_NOT_EXCLUSIVE')
    p=positions[0]
    if (p.get('symbol')!='ETHUSDT' or p.get('marginType') not in ('ISOLATED','ISOLATE')
        or any(str(p.get(k))!=str(expected_position.get(k)) for k in ('id','side','size'))
        or p.get('side') not in ('LONG','SHORT') or positive(p.get('size')) is None):
        return deny('POSITION_IDENTITY_NOT_BOUND')
    if not conditional:
        return {'readyToDispatchEmergency':True,'canCancel':False,
                'reason':'NO_CONDITIONAL_STOP_ACTIVE','exchangeWrites':0,
                'requiresFreshReadbackBeforeDispatch':True}
    if len(conditional)!=1 or not isinstance(expected_stop,dict):
        return deny('UNKNOWN_OR_MULTIPLE_CONDITIONAL_ORDERS')
    c=conditional[0]
    if (not isinstance(c,dict) or not expected_stop.get('algoId')
        or str(c.get('algoId'))!=str(expected_stop['algoId'])
        or c.get('symbol')!='ETHUSDT' or c.get('positionSide')!=p['side']
        or c.get('reduceOnly') is not True
        or str(c.get('algoStatus','')).upper() not in ACTIVE
        or c.get('side') not in (None,'SELL' if p['side']=='LONG' else 'BUY')):
        return deny('CONDITIONAL_STOP_NOT_UNIQUELY_OWNED_ACTIVE')
    if c.get('orderType') not in ('STOP_MARKET','STOP_LOSS_MARKET'):
        return deny('NOT_KNOWN_STOP_ORDER_TYPE')
    if (c.get('closePosition') is not True and
        positive(c.get('quantity'))!=positive(p.get('size'))):
        return deny('STOP_QUANTITY_NOT_FULL_POSITION')
    if (positive(c.get('triggerPrice')) is None or
        positive(expected_stop.get('triggerPrice'))!=positive(c.get('triggerPrice'))):
        return deny('STOP_TRIGGER_PRICE_NOT_EXACT')
    return deny('STOP_ACTIVE_CANCEL_CONFIRMATION_REQUIRED_BEFORE_POSITION_CLOSE',
                exactAlgoId=str(c['algoId']),positionId=str(p['id']),
                mustReobserveAfterCancellation=True)
