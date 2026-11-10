"""Bind WEEX V3 userTrades to a bot position via verified order ownership.

Raw WEEX /userTrades does NOT include positionId. Never infer ownership
from symbol alone. Only an exact previously verified exit order ID can
authorize converting an exchange fill for position-ledger reconciliation.
Offline data transformation; no exchange writes or private API reads.
"""
from weex_tp_limit_shadow import decimal

def bind_exit_fills(*,position_id,symbol,side,verified_exit_order_ids,
                    raw_fills,order_history):
    if not position_id or not isinstance(symbol,str) or side not in ('LONG','SHORT'):
        raise ValueError('POSITION_IDENTITY_MISSING')
    if not isinstance(verified_exit_order_ids,(set,list,tuple)) or not verified_exit_order_ids:
        raise ValueError('NO_VERIFIED_OWNED_EXIT_ORDERS')
    if not isinstance(raw_fills,list) or not isinstance(order_history,list):
        raise ValueError('INCOMPLETE_EXCHANGE_HISTORY')
    owned={str(x) for x in verified_exit_order_ids if x is not None}
    if len(owned)!=len(verified_exit_order_ids):
        raise ValueError('DUPLICATED_OWNED_ORDER_ID')
    exit_side='SELL' if side=='LONG' else 'BUY'
    matched={}
    for order in order_history:
        if not isinstance(order,dict):raise ValueError('INVALID_ORDER_HISTORY')
        order_id=str(order.get('orderId'))
        if order_id in owned:
            if order_id in matched:raise ValueError('DUPLICATED_VERIFIED_ORDER')
            if (order.get('symbol')!=symbol or order.get('positionSide')!=side
                or order.get('side')!=exit_side or order.get('reduceOnly') is not True):
                raise ValueError('VERIFIED_ORDER_NOT_CLOSE_ONLY')
            matched[order_id]=order
    if set(matched)!=owned:
        raise ValueError('VERIFIED_ORDERS_MISSING_FROM_HISTORY')
    normalized=[];ids=set()
    for fill in raw_fills:
        if not isinstance(fill,dict):raise ValueError('INVALID_USER_TRADE')
        oid=str(fill.get('orderId'))
        if oid not in owned:
            # Unrelated orders are not automatically attributed to this position.
            continue
        fid=str(fill.get('id'))
        if not fid or fid=='None' or fid in ids:
            raise ValueError('DUPLICATED_OR_MISSING_FILL_ID')
        ids.add(fid)
        if ('positionId' in fill and str(fill['positionId'])!=str(position_id)):
            raise ValueError('CONFLICTING_FILL_POSITION_ID')
        if (fill.get('symbol')!=symbol or fill.get('positionSide')!=side
            or fill.get('side')!=exit_side or fill.get('commissionAsset')!='USDT'):
            raise ValueError('FILL_NOT_MATCHED_TO_OWNED_ORDER')
        if decimal(fill.get('qty'))<=0 or decimal(fill.get('price'))<=0 or decimal(fill.get('commission'))<0:
            raise ValueError('INVALID_EXIT_ECONOMICS')
        normalized.append({**fill,'positionId':str(position_id)})
    for oid,order in matched.items():
        count=sum((decimal(f['qty']) for f in normalized if str(f['orderId'])==oid),decimal(0))
        if count!=decimal(order.get('executedQty')):
            raise ValueError('INCOMPLETE_OR_REGRESSED_EXIT_HISTORY')
    return {'status':'ORDER_BOUND_ONLY','normalized':normalized,
            'exchangePositionIdPresent':all('positionId' in f for f in raw_fills if str(f.get('orderId')) in owned),
            'exitOrderIds':sorted(owned),
            'readyForPositionReconciliation':True,
            'ordersSubmitted':False,'canRetry':False}
