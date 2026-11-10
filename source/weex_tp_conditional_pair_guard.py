"""WEEX conditional TP LIMIT + SL read-only pair audit.

V3 supports executePrice>0 for TP LIMIT and executePrice=0 for SL MARKET.
This code never submits orders. Two orders being active does NOT prove OCO
semantics, reservation compatibility, stop fill, or cancellation on TP fills.
"""
from weex_tp_limit_shadow import decimal
from weex_http_guard import prepare_sdk_request

def plan_stop(*,trade_id,symbol,position_side,quantity,stop_trigger_price,
              entry_mean_price,trigger_price_type='MARK_PRICE'):
    if not trade_id or not symbol or position_side not in ('LONG','SHORT'):
        raise ValueError('INVALID_STOP_IDENTITY')
    if trigger_price_type not in ('MARK_PRICE','CONTRACT_PRICE'):
        raise ValueError('INVALID_TRIGGER_SOURCE')
    q=decimal(quantity);stop=decimal(stop_trigger_price);entry=decimal(entry_mean_price)
    if q<=0 or stop<=0 or entry<=0:raise ValueError('INVALID_STOP_VALUES')
    if position_side=='LONG' and stop>=entry:raise ValueError('STOP_NOT_ADVERSE_FOR_LONG')
    if position_side=='SHORT' and stop<=entry:raise ValueError('STOP_NOT_ADVERSE_FOR_SHORT')
    request={'symbol':symbol,'clientAlgoId':'wxsl_'+str(trade_id)[-24:],
             'planType':'STOP_LOSS','triggerPrice':str(stop),
             'executePrice':'0','quantity':str(q),
             'positionSide':position_side,'triggerPriceType':trigger_price_type,
             'reduceOnly':True,'closePosition':False}
    check=prepare_sdk_request('post_capi_v3_placeTpSlOrder',request)
    if check['networkRequests']!=0:raise ValueError('OFFLINE_GUARD_FAILED')
    return {'status':'PREPARED_OFFLINE_ONLY','request':request,'sdkPreview':check,
            'dispatchAllowed':False,'stopExecutionPriceGuaranteed':False}

def check_pair(*,tp_plan,sl_plan,position,observed_algos,regular_orders,
               expected_remaining=None):
    base={'state':'REVIEW_REQUIRED','dispatchAllowed':False,'canRetry':False,
          'stopProtectionVerified':False,'liveEntryAllowed':False,'ocoCertified':False}
    if not isinstance(position,dict) or not isinstance(observed_algos,list) or not isinstance(regular_orders,list):
        return {**base,'reason':'INCOMPLETE_SNAPSHOT'}
    try:
        tp=tp_plan['request'];sl=sl_plan['request']
        if (tp.get('planType')!='TAKE_PROFIT' or decimal(tp['executePrice'])<=0
            or sl.get('planType')!='STOP_LOSS' or decimal(sl['executePrice'])!=0):
            raise ValueError('TP_SL_PLAN_TYPES_INVALID')
        if (tp['symbol']!=sl['symbol'] or tp['positionSide']!=sl['positionSide']
            or decimal(tp['quantity'])!=decimal(sl['quantity'])
            or tp['clientAlgoId']==sl['clientAlgoId']):
            raise ValueError('PAIR_PLAN_MISMATCH')
        if (position.get('symbol')!=tp['symbol'] or position.get('side')!=tp['positionSide']):
            raise ValueError('POSITION_IDENTITY_CHANGED')
        remaining=decimal(position.get('size'))
        if expected_remaining is not None and remaining!=decimal(expected_remaining):
            raise ValueError('POSITION_QUANTITY_CHANGED')
        if not 0<=remaining<=decimal(tp['quantity']):
            raise ValueError('POSITION_QUANTITY_OUTSIDE_PLAN')
        if any(o.get('symbol')==tp['symbol'] for o in regular_orders):
            raise ValueError('UNACCOUNTED_REGULAR_EXIT_ORDER')
        matches={}
        for name,request in (('TP',tp),('SL',sl)):
            found=[a for a in observed_algos if a.get('clientAlgoId')==request['clientAlgoId']]
            if len(found)!=1:raise ValueError(name+'_ORDER_MISSING_OR_DUPLICATED')
            a=found[0]
            if (not a.get('algoId') or a.get('symbol')!=request['symbol']
                or a.get('positionSide')!=request['positionSide']
                or a.get('side')!=('SELL' if request['positionSide']=='LONG' else 'BUY')
                or a.get('reduceOnly') is not True
                or decimal(a.get('quantity'))!=decimal(request['quantity'])
                or decimal(a.get('triggerPrice'))!=decimal(request['triggerPrice'])
                or a.get('workingType')!=request['triggerPriceType']):
                raise ValueError(name+'_ORDER_FIELDS_CHANGED')
            # V3 response orderType should identify market vs limit.
            if name=='TP':
                if a.get('orderType') not in ('TAKE_PROFIT','TAKE_PROFIT_LIMIT'):
                    raise ValueError('TP_LIMIT_EXECUTION_NOT_CONFIRMED')
                observed_price=a.get('price',a.get('executePrice'))
                if observed_price is None or decimal(observed_price)!=decimal(request['executePrice']):
                    raise ValueError('TP_EXECUTION_PRICE_UNVERIFIED')
            else:
                if a.get('orderType') not in ('STOP_LOSS','STOP_LOSS_MARKET','STOP_MARKET'):
                    raise ValueError('STOP_ORDER_TYPE_UNVERIFIED')
                observed_price=a.get('price',a.get('executePrice'))
                if observed_price is not None and decimal(observed_price)!=0:
                    raise ValueError('STOP_NOT_MARKET_EXECUTION')
            if a.get('algoStatus') not in ('NEW','UNTRIGGERED'):
                raise ValueError(name+'_TRIGGERED_OR_INACTIVE_RECONCILE')
            matches[name]=str(a['algoId'])
        if matches['TP']==matches['SL']:raise ValueError('ORDER_IDS_COLLIDE')
        # A partial fill can leave old full-size SL/TP quantities outstanding.
        if remaining!=decimal(tp['quantity']):
            return {**base,'state':'PARTIAL_POSITION_REQUIRES_EXIT_RECONCILIATION',
                    'reason':'TRIGGERS_STILL_REFERENCE_ORIGINAL_QUANTITY',
                    'remainingQuantity':str(remaining),'orderIds':matches}
        return {**base,'state':'PAIR_OBSERVED_NOT_CERTIFIED',
                'reason':'SIMULTANEOUS_COVERAGE_AND_OCO_UNPROVEN',
                'remainingQuantity':str(remaining),'orderIds':matches}
    except (KeyError,TypeError,ValueError,ArithmeticError) as exc:
        return {**base,'reason':str(exc)}
