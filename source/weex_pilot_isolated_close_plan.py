"""Exact-scope Isolated 1x pilot emergency close preflight; no HTTP writes.

Requires a locally journaled pilot entry and its authenticated exchange order,
fills and exactly one fresh attributable position. Returns an unsigned proposal
only; never authorizes transport or blindly closes an existing manual position.
"""
from decimal import Decimal,InvalidOperation

def plan(*,pilot,entry_order,entry_fills,positions,regular_orders,algos,observed_fresh):
    blocked=lambda reason:{'prepared':False,'canSend':False,'reason':reason,'exchangeWrites':0}
    if observed_fresh is not True:return blocked('STALE_ACCOUNT_OBSERVATION')
    if not isinstance(pilot,dict) or not isinstance(entry_order,dict):
        return blocked('MISSING_PILOT_IDENTITY')
    if not all(isinstance(x,list) for x in (entry_fills,positions,regular_orders,algos)):
        return blocked('ACCOUNT_OR_FILLS_INCOMPLETE')
    if regular_orders or algos:return blocked('OPEN_ORDERS_REQUIRE_RECONCILIATION')
    if len(positions)!=1:return blocked('EXACTLY_ONE_POSITION_REQUIRED')
    position=positions[0]
    try:
        side=pilot['side']
        if side not in ('LONG','SHORT'):return blocked('INVALID_SIDE')
        qty=Decimal(str(pilot['quantity']))
        pqty=Decimal(str(position['size']))
        fills_qty=sum((Decimal(str(f['qty'])) for f in entry_fills),Decimal(0))
        if not all(x.is_finite() and x>0 for x in (qty,pqty,fills_qty)) or qty!=pqty or qty!=fills_qty:
            return blocked('POSITION_FILL_QUANTITY_MISMATCH')
        cid=pilot['entryId']
        if not cid or entry_order.get('clientOrderId')!=cid:
            return blocked('UNBOUND_ENTRY')
        oid=str(entry_order['orderId'])
        if not oid or not entry_fills or any(str(f.get('orderId'))!=oid for f in entry_fills):
            return blocked('ENTRY_FILLS_NOT_ORDER_BOUND')
        if len({str(f.get('id') or '') for f in entry_fills})!=len(entry_fills) or any(not f.get('id') for f in entry_fills):
            return blocked('FILL_IDENTITIES_NOT_UNIQUE')
        direction='BUY' if side=='LONG' else 'SELL'
        if (entry_order.get('status')!='FILLED' or entry_order.get('symbol')!='ETHUSDT'
            or entry_order.get('positionSide')!=side or entry_order.get('side')!=direction
            or position.get('symbol')!='ETHUSDT' or position.get('side')!=side
            or position.get('marginType') not in ('ISOLATED','ISOLATE')
            or position.get('manualOrMixed') is not False):
            return blocked('POSITION_OR_ENTRY_NOT_ATTRIBUTED')
        if any(f.get('symbol')!='ETHUSDT' or f.get('side')!=direction or f.get('positionSide')!=side for f in entry_fills):
            return blocked('ENTRY_FILL_IDENTITY_MISMATCH')
        close_cid=pilot['closeId']
        if not close_cid or close_cid==cid:return blocked('INVALID_CLOSE_CLIENT_ID')
        return {'prepared':True,'canSend':False,'exchangeWrites':0,
                'requestMethod':'POST','operation':'post_capi_v3_order',
                'payload':{'symbol':'ETHUSDT','side':'SELL' if side=='LONG' else 'BUY',
                           'positionSide':side,'type':'MARKET',
                           'quantity':str(qty),'reduceOnly':True,
                           'newClientOrderId':close_cid},
                'reason':'OFFLINE_PROPOSAL_REQUIRES_SEPARATE_AUTHORISER_AND_EXCHANGE_RECHECK'}
    except (KeyError,TypeError,ValueError,InvalidOperation,ArithmeticError):
        return blocked('INVALID_EXCHANGE_VALUES')
