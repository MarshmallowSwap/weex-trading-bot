"""WEEX fixed-net-PnL LIMIT exit, offline proposal and settlement only.

No API requests. Live strategy migration is deliberately unsupported here.
A resting GTC limit can remain unfilled; NOT a protective stop loss.
"""
from decimal import Decimal, InvalidOperation
from weex_tp_pnl_preview import preview as pnl_price
from weex_http_guard import prepare_sdk_request

def decimal(value):
    try:
        x=Decimal(str(value))
        if not x.is_finite():raise ValueError()
        return x
    except (ValueError,TypeError,InvalidOperation):
        raise ValueError('INVALID_DECIMAL')

def propose(*,trade_id,symbol,position_id,side,quantity,entry_cost_usdt,
            entry_fees_usdt,exit_fee_rate,target_net_usdt,price_tick,
            position_observation,regular_orders,conditional_orders):
    if not trade_id or not symbol or not position_id or side not in ('LONG','SHORT'):
        raise ValueError('INVALID_POSITION_IDENTITY')
    if not isinstance(position_observation,dict) or not isinstance(regular_orders,list) or not isinstance(conditional_orders,list):
        raise ValueError('UNVERIFIED_ACCOUNT_OBSERVATION')
    p=position_observation
    q=decimal(quantity);cost=decimal(entry_cost_usdt);fees=decimal(entry_fees_usdt)
    if (str(p.get('id'))!=str(position_id) or p.get('symbol')!=symbol
        or p.get('side')!=side or decimal(p.get('size'))!=q
        or decimal(p.get('openValue'))!=cost or decimal(p.get('openFee'))!=fees):
        raise ValueError('POSITION_OWNERSHIP_OR_ECONOMICS_CHANGED')
    if any(o.get('symbol')==symbol for o in regular_orders+conditional_orders):
        raise ValueError('EXISTING_SYMBOL_ORDER_REQUIRES_RECONCILIATION')
    pnl=pnl_price(side=side,quantity=q,entry_cost_usdt=cost,
                  entry_fees_usdt=fees,exit_fee_rate=exit_fee_rate,
                  target_net_usdt=target_net_usdt,price_tick=price_tick)
    request={'symbol':symbol,'side':'SELL' if side=='LONG' else 'BUY',
             'positionSide':side,'type':'LIMIT','timeInForce':'GTC',
             'price':pnl['triggerPrice'],'quantity':str(q),
             'reduceOnly':True,'newClientOrderId':'wxlmt_'+str(trade_id)[-24:]}
    result=prepare_sdk_request('post_capi_v3_order',request)
    if result['ordersSubmitted'] is not False or result['networkRequests']!=0:
        raise ValueError('NETWORK_PREVIEW_NOT_OFFLINE')
    return {'status':'PREPARED_OFFLINE_ONLY','strategy':'FIXED_NET_LIMIT',
            'requestedNetUSDT':str(decimal(target_net_usdt)),
            'estimatedNetAtLimitUSDT':pnl['estimatedNetAtTriggerUSDT'],
            'request':request,'entryAudit':{'costUSDT':str(cost),'feesUSDT':str(fees)},
            'sdkPreview':result,'dispatchAllowed':False,
            'exchangeOrderConfirmed':False,'protectiveStopConfirmed':False,
            'note':'Limit price protects execution price, not fill probability.'}

def reconcile_fills(*,order_id,side,entry_quantity,entry_cost_usdt,entry_fees_usdt,
                    exit_fills,remaining_position_quantity):
    if side not in ('LONG','SHORT') or not order_id or not isinstance(exit_fills,list):
        raise ValueError('INVALID_EXIT')
    entry_qty=decimal(entry_quantity);cost=decimal(entry_cost_usdt);entry_fees=decimal(entry_fees_usdt)
    remaining=decimal(remaining_position_quantity)
    if entry_qty<=0 or cost<=0 or entry_fees<0 or remaining<0:
        raise ValueError('INVALID_ENTRY_ECONOMICS')
    seen=set();closed=Decimal(0);value=Decimal(0);fees=Decimal(0)
    expected_side='SELL' if side=='LONG' else 'BUY'
    for f in exit_fills:
        if not isinstance(f,dict) or not f.get('id') or str(f['id']) in seen:
            raise ValueError('DUPLICATE_OR_INVALID_FILL')
        if (str(f.get('orderId'))!=str(order_id) or f.get('positionSide')!=side
            or f.get('side')!=expected_side or f.get('commissionAsset')!='USDT'):
            raise ValueError('EXIT_FILL_NOT_BOUND')
        seen.add(str(f['id']))
        q=decimal(f['qty']);px=decimal(f['price']);fee=decimal(f['commission'])
        if q<=0 or px<=0 or fee<0:raise ValueError('INVALID_EXIT_FILL')
        closed+=q;value+=q*px;fees+=fee
    if closed>entry_qty or remaining+closed!=entry_qty:
        raise ValueError('EXIT_QUANTITY_NOT_RECONCILED')
    if not closed:
        return {'status':'OPEN_UNFILLED','quantityClosed':'0',
                'remainingQuantity':str(remaining),'netRealizedBeforeFundingUSDT':'0'}
    fraction=closed/entry_qty
    allocated_cost=cost*fraction;allocated_entry_fees=entry_fees*fraction
    gross=(value-allocated_cost) if side=='LONG' else (allocated_cost-value)
    net=gross-allocated_entry_fees-fees
    return {'status':'CLOSED_VERIFIED' if remaining==0 else 'PARTIALLY_FILLED',
            'quantityClosed':str(closed),'remainingQuantity':str(remaining),
            'netRealizedBeforeFundingUSDT':str(net),'exitFeesUSDT':str(fees),
            'fundingIncluded':False}
