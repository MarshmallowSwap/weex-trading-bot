"""Conservative TP LIMIT + SL capacity gate, offline only.

WEEX position-close available quantity can be reserved by resting LIMIT exits;
therefore LIMIT+SL full simultaneous coverage is NOT assumed. This guard
requires independently proven exchange compatibility before enabling a plan.
"""
from weex_tp_limit_shadow import decimal

def assess(position,limit_order,sl_order,*,exchange_verified_shared_coverage=False,
           fresh_account_evidence=False):
    out={'status':'BLOCKED','ordersSubmitted':False,'dispatchAllowed':False,
         'liveEntryAllowed':False,'reason':'UNVERIFIED_TP_LIMIT_SL_COMPATIBILITY',
         'stopProtectionVerified':False}
    if not isinstance(position,dict) or not isinstance(limit_order,dict) or not isinstance(sl_order,dict):
        return {**out,'reason':'INCOMPLETE_EVIDENCE'}
    try:
        side=position['side'];symbol=position['symbol']
        if side not in ('LONG','SHORT'):raise ValueError('INVALID_SIDE')
        q=decimal(position['size'])
        if q<=0:raise ValueError('INVALID_POSITION_QUANTITY')
        exit_side='SELL' if side=='LONG' else 'BUY'
        for o in (limit_order,sl_order):
            if o.get('symbol')!=symbol or o.get('positionSide')!=side or o.get('side')!=exit_side or o.get('reduceOnly') is not True:
                raise ValueError('ORDER_NOT_BOUND_TO_POSITION')
        if limit_order.get('type')!='LIMIT' or limit_order.get('timeInForce')!='GTC':
            raise ValueError('NOT_RESTING_LIMIT')
        if sl_order.get('orderType') not in ('STOP_MARKET','STOP_LOSS_MARKET','STOP'):
            raise ValueError('NOT_STOP_LOSS_ORDER')
        if sl_order.get('algoStatus') not in ('NEW','UNTRIGGERED'):
            raise ValueError('STOP_NOT_ACTIVE')
        lq=decimal(limit_order.get('origQty',limit_order.get('quantity')))
        sq=decimal(sl_order.get('quantity'))
        if lq<=0 or sq<=0 or lq!=q or sq!=q:
            raise ValueError('FULL_POSITION_COVERAGE_NOT_OBSERVED')
        if not fresh_account_evidence:
            return {**out,'reason':'ACCOUNT_EVIDENCE_NOT_FRESH'}
        if not exchange_verified_shared_coverage:
            return {**out,'reason':'SIMULTANEOUS_COVERAGE_NOT_CERTIFIED'}
        # Caller must have independent evidence that exchange actually permits
        # both close-only orders across partial fills. The caller cannot infer
        # this flag from documented endpoint fields or an offline test.
        return {'status':'CANDIDATE_VERIFIED_OFFLINE','ordersSubmitted':False,
                'dispatchAllowed':False,'liveEntryAllowed':False,
                'reason':'REQUIRES_EXCHANGE_CERTIFIED_PARTIAL_FILL_POLICY',
                'stopProtectionVerified':False}
    except (KeyError,TypeError,ValueError,ArithmeticError) as exc:
        return {**out,'reason':str(exc)}

def residual_check(position,limit_order,stop_order):
    """Only inspect residual quantities; never cancel/replace automatically."""
    if not isinstance(position,dict) or not isinstance(limit_order,dict) or not isinstance(stop_order,dict):
        return {'state':'REVIEW_REQUIRED','reason':'MISSING_EXIT_OBSERVATION','actionsAllowed':False}
    try:
        remaining=decimal(position.get('size'))
        lq=decimal(limit_order.get('remainingQty'))
        sq=decimal(stop_order.get('quantity'))
        if any(x<0 for x in (remaining,lq,sq)):
            raise ValueError('NEGATIVE_REMAINING')
        if remaining==0:
            if lq>0 or sq>0:
                return {'state':'REVIEW_REQUIRED','reason':'STALE_CLOSING_ORDERS_AFTER_CLOSE','actionsAllowed':False}
            return {'state':'CLOSED_OBSERVED','actionsAllowed':False}
        if lq!=remaining or sq!=remaining:
            return {'state':'REVIEW_REQUIRED','reason':'EXIT_QUANTITY_NOT_SYNCHRONIZED','actionsAllowed':False,
                    'remainingPosition':str(remaining),'limitRemaining':str(lq),'stopQuantity':str(sq)}
        return {'state':'QUANTITIES_MATCH_NOT_CERTIFIED','actionsAllowed':False,
                'stopProtectionVerified':False}
    except (KeyError,TypeError,ValueError,ArithmeticError) as exc:
        return {'state':'REVIEW_REQUIRED','reason':str(exc),'actionsAllowed':False}
