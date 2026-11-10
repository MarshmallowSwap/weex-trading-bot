"""GET-only adapter for the offline WEEX net LIMIT journal.

No order submission, no cancellation, no live strategy migration. A missing
order remains missing: never infer exchange acceptance from a local proposal.
"""
import time
from weex_execution_readonly import pages
from weex_tp_limit_shadow import decimal

def inspect(reader,proposal,*,now_ms=None):
    """reader(operation, **params) is injected; no credentials in this module."""
    request=proposal['request'];symbol=request['symbol'];client=request['newClientOrderId']
    start=time.monotonic()
    result={'state':'UNKNOWN','dispatchAllowed':False,'ordersSubmitted':False,
            'canRetry':False,'symbol':symbol,'clientOrderId':client,
            'exchangeOrderConfirmed':False,'protectiveStopConfirmed':False}
    try:
        now=int(time.time()*1000) if now_ms is None else now_ms
        opened=pages(reader,'get_capi_v3_openOrders',identity='orderId',start=0,symbol=symbol)
        history=pages(reader,'get_capi_v3_order_history',identity='orderId',start=0,
                      symbol=symbol,startTime=now-86400000,endTime=now)
        orders={}
        for order in history+opened:
            oid=str(order['orderId'])
            if oid in orders and any(order.get(k)!=orders[oid].get(k) for k in
                                     ('clientOrderId','symbol','side','positionSide',
                                      'status','executedQty','price')):
                raise ValueError('CHANGING_ORDER_SNAPSHOT')
            orders[oid]=order
        matching=[o for o in orders.values() if o.get('clientOrderId')==client]
        if len(matching)>1:raise ValueError('DUPLICATE_CLIENT_ORDER_ID')
        positions=reader('get_capi_v3_account_position_allPosition')
        algos=pages(reader,'get_capi_v3_openAlgoOrders',identity='algoId',start=1,symbol=symbol)
        if not isinstance(positions,list):raise ValueError('INVALID_POSITION_SNAPSHOT')
        own=[p for p in positions if p.get('symbol')==symbol]
        if len(own)>1:raise ValueError('AMBIGUOUS_POSITION')
        # A take-profit LIMIT is NOT a stop loss. Do not claim a protective stop.
        # Do not ignore live conditional orders merely because they differ from LIMIT.
        active_algos=[a for a in algos if a.get('symbol')==symbol]
        result.update(protectiveStopConfirmed=False,conditionalOrdersObserved=len(active_algos),
                      positionPresent=len(own)==1)
        if not matching:
            result['state']='NO_MATCHING_EXCHANGE_ORDER'
            return result
        o=matching[0]
        if (o.get('symbol')!=symbol or o.get('side')!=request['side']
            or o.get('positionSide')!=request['positionSide']
            or o.get('type')!='LIMIT' or o.get('reduceOnly') is not True
            or decimal(o.get('price'))!=decimal(request['price'])
            or decimal(o.get('origQty'))!=decimal(request['quantity'])):
            raise ValueError('MATCHED_ORDER_FIELDS_CONFLICT')
        if o.get('timeInForce') not in (None,'GTC'):
            raise ValueError('WRONG_TIME_IN_FORCE')
        fills=reader('get_capi_v3_userTrades',symbol=symbol,orderId=o['orderId'],limit=100)
        if not isinstance(fills,list) or len(fills)>=100:raise ValueError('INCOMPLETE_EXIT_FILLS')
        executed=decimal(o.get('executedQty'))
        total=sum((decimal(x.get('qty')) for x in fills),decimal(0))
        if executed!=total:raise ValueError('EXECUTED_QTY_DIFFERS_FROM_FILLS')
        if len(own)==1:
            p=own[0]
            if p.get('side')!=request['positionSide']:
                raise ValueError('POSITION_SIDE_CHANGED')
            remaining=decimal(p.get('size'))
        else:
            remaining=decimal(0)
        if remaining+executed!=decimal(request['quantity']):
            raise ValueError('POSITION_AND_FILL_QUANTITIES_DISAGREE')
        if time.monotonic()-start>5:
            raise ValueError('SNAPSHOT_TOO_SLOW')
        result.update(state='MATCHED_READ_ONLY',exchangeOrderConfirmed=True,
                      order=o,fills=fills,remainingQuantity=str(remaining))
        return result
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        result['state']='REVIEW_REQUIRED'
        result['reason']=str(exc)
        return result
    except Exception as exc:
        result['state']='READ_UNAVAILABLE'
        result['reason']=type(exc).__name__
        return result

def reconcile(reader,journal_path,trade_id,proposal,*,now_ms=None):
    """Read exchange first; journal updated only on independently bound evidence."""
    snapshot=inspect(reader,proposal,now_ms=now_ms)
    if snapshot['state']!='MATCHED_READ_ONLY':
        return snapshot
    from weex_tp_limit_journal import observe
    settled=observe(journal_path,trade_id,snapshot['order'],snapshot['fills'],
                    snapshot['remainingQuantity'])
    return {**snapshot,'journalState':settled['state'],'evidence':settled.get('evidence'),
            'dispatchAllowed':False,'canRetry':False}
