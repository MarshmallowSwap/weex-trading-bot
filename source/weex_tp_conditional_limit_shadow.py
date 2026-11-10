"""WEEX V3 conditional TP with limit execution: OFFLINE proposal.

The TP is triggered by triggerPrice, then places an exit LIMIT at executePrice.
No exchange calls, no dispatch, and no claim of simultaneous full-position SL.
"""
from decimal import Decimal
from weex_tp_limit_shadow import decimal
from weex_tp_pnl_preview import preview
from weex_http_guard import prepare_sdk_request

def prepare(*,trade_id,symbol,position_id,side,quantity,entry_cost_usdt,
            entry_fees_usdt,exit_fee_rate,target_net_usdt,price_tick,
            position_observation,regular_orders,conditional_orders,
            trigger_price_type='CONTRACT_PRICE',copy_trading_key=False):
    if copy_trading_key:
        raise ValueError('COPY_TRADING_KEY_REQUIRES_MARKET_EXIT')
    if side not in ('LONG','SHORT') or trigger_price_type not in ('MARK_PRICE','CONTRACT_PRICE'):
        raise ValueError('INVALID_SIDE_OR_TRIGGER_SOURCE')
    if not all(isinstance(x,str) and x for x in (trade_id,symbol,position_id)):
        raise ValueError('INVALID_IDENTIFIERS')
    if not isinstance(position_observation,dict) or not isinstance(regular_orders,list) or not isinstance(conditional_orders,list):
        raise ValueError('MISSING_EXCHANGE_EVIDENCE')
    q=decimal(quantity);cost=decimal(entry_cost_usdt);fee=decimal(entry_fees_usdt)
    p=position_observation
    if (q<=0 or p.get('symbol')!=symbol or str(p.get('id'))!=position_id
            or p.get('side')!=side or decimal(p.get('size'))!=q
            or decimal(p.get('openValue'))!=cost or decimal(p.get('openFee'))!=fee):
        raise ValueError('ENTRY_POSITION_MISMATCH')
    if any(o.get('symbol')==symbol for o in regular_orders+conditional_orders):
        raise ValueError('PREEXISTING_EXIT_REQUIRES_RECONCILIATION')
    target=preview(side=side,quantity=q,entry_cost_usdt=cost,entry_fees_usdt=fee,
                   exit_fee_rate=exit_fee_rate,target_net_usdt=target_net_usdt,
                   price_tick=price_tick)
    price=target['triggerPrice']
    # The trigger is set to the limit price. A gap across the trigger can
    # leave the resulting limit order unfilled indefinitely.
    request={'symbol':symbol,'clientAlgoId':'wxclmt_'+str(trade_id)[-24:],
             'planType':'TAKE_PROFIT','triggerPrice':price,'executePrice':price,
             'quantity':str(q),'positionSide':side,
             'triggerPriceType':trigger_price_type,'reduceOnly':True,
             'closePosition':False}
    if len(request['clientAlgoId'])>36:
        raise ValueError('CLIENT_ID_TOO_LONG')
    serial=prepare_sdk_request('post_capi_v3_placeTpSlOrder',request)
    if serial['networkRequests']!=0 or serial['ordersSubmitted'] is not False:
        raise ValueError('UNSAFE_SERIALIZATION')
    return {'status':'PREPARED_OFFLINE_ONLY','mode':'CONDITIONAL_NET_LIMIT',
            'request':request,'entryAudit':{'costUSDT':str(cost),'feesUSDT':str(fee)},
            'targetNetUSDT':str(decimal(target_net_usdt)),
            'estimatedNetIfFullyExecutedAtLimitUSDT':target['estimatedNetAtTriggerUSDT'],
            'sdkPreview':serial,'dispatchAllowed':False,
            'stopLossCompatibilityVerified':False,
            'marketGapMayLeaveLimitUnfilled':True,
            'fundingIncluded':False}

def inspect_conditional(*,proposal,algo_orders,position,sl_orders):
    """Check state and SL coexistence without claiming a safe automatic exit."""
    result={'state':'REVIEW_REQUIRED','dispatchAllowed':False,'safeToEnterLive':False,
            'stopLossCompatibilityVerified':False,'canRetry':False}
    if (not isinstance(proposal,dict) or not isinstance(algo_orders,list)
            or not isinstance(sl_orders,list) or not isinstance(position,dict)):
        return {**result,'reason':'INCOMPLETE_SNAPSHOT'}
    req=proposal.get('request',{})
    matching=[a for a in algo_orders if a.get('clientAlgoId')==req.get('clientAlgoId')]
    if len(matching)!=1:return {**result,'reason':'TP_NOT_UNIQUELY_OBSERVED'}
    a=matching[0]
    try:
        if (a.get('symbol')!=req['symbol']
            or a.get('positionSide')!=req['positionSide']
            or a.get('orderType') not in ('TAKE_PROFIT','TAKE_PROFIT_LIMIT')
            or a.get('reduceOnly') is not True
            or decimal(a.get('quantity'))!=decimal(req['quantity'])
            or decimal(a.get('triggerPrice'))!=decimal(req['triggerPrice'])
            or decimal(a.get('price',a.get('executePrice')))!=decimal(req['executePrice'])
            or a.get('workingType')!=req['triggerPriceType']):
            raise ValueError('TP_CONDITIONAL_FIELDS_CHANGED')
        if (position.get('symbol')!=req['symbol'] or position.get('side')!=req['positionSide']
            or decimal(position.get('size'))>decimal(req['quantity'])):
            raise ValueError('POSITION_MISMATCH')
        if a.get('algoStatus') not in ('NEW','UNTRIGGERED'):
            return {**result,'state':'TRIGGERED_OR_INACTIVE_RECONCILE_EXECUTION',
                    'reason':'MUST_READ_EXECUTION_HISTORY'}
        # Even with a recorded stop, WEEX may reserve the same close quantity.
        return {**result,'state':'TP_OBSERVED_SL_COVERAGE_UNVERIFIED',
                'conditionalTpId':str(a.get('algoId')),
                'stopOrdersSeen':len(sl_orders),
                'reason':'NEEDS_EXCHANGE_PROOF_OF_SIMULTANEOUS_COVERAGE'}
    except (KeyError,ValueError,TypeError,ArithmeticError) as exc:
        return {**result,'reason':str(exc)}
