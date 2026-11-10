"""Persistent shadow-only WEEX limit-TP audit ledger.

No transport, no exchange writes. Immutable intent -> observed order/fills.
Only exact client-order identity may advance. Missing/ambiguous observations
block, never request a retry.
"""
import hashlib,json,sqlite3
from contextlib import closing
from pathlib import Path
from weex_tp_limit_shadow import reconcile_fills,decimal

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def connect(path):
    db=sqlite3.connect(path)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA synchronous=FULL')
    db.execute('''CREATE TABLE IF NOT EXISTS shadow_limit_v1(
        trade_id TEXT PRIMARY KEY, proposal_sha256 TEXT NOT NULL,
        proposal_json TEXT NOT NULL, state TEXT NOT NULL,
        exchange_order_id TEXT, last_evidence_json TEXT)''')
    return db

def register(path,trade_id,proposal):
    if (proposal.get('status')!='PREPARED_OFFLINE_ONLY'
        or proposal.get('strategy')!='FIXED_NET_LIMIT'
        or proposal.get('dispatchAllowed') is not False
        or proposal.get('sdkPreview',{}).get('networkRequests')!=0):
        raise ValueError('NOT_VERIFIED_OFFLINE_PROPOSAL')
    req=proposal['request']
    if not trade_id or req.get('type')!='LIMIT' or req.get('timeInForce')!='GTC' or req.get('reduceOnly') is not True:
        raise ValueError('NOT_CLOSE_ONLY_LIMIT')
    h=digest(proposal)
    with closing(connect(path)) as db,db:
        current=db.execute('SELECT proposal_sha256,state FROM shadow_limit_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        if current:
            if current['proposal_sha256']!=h:raise ValueError('IMMUTABLE_SHADOW_PROPOSAL_CHANGED')
            return {'state':current['state'],'alreadyRegistered':True,'dispatchAllowed':False}
        db.execute('INSERT INTO shadow_limit_v1 VALUES(?,?,?, ?,NULL,NULL)',
                   (trade_id,h,canonical(proposal),'PREPARED_NOT_SENT'))
    return {'state':'PREPARED_NOT_SENT','alreadyRegistered':False,'dispatchAllowed':False}

def observe(path,trade_id,order,exit_fills,remaining_quantity):
    """Observe ONLY externally provided read-only evidence; no order submission."""
    with closing(connect(path)) as db,db:
        record=db.execute('SELECT * FROM shadow_limit_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        if record is None:raise ValueError('UNKNOWN_SHADOW_PROPOSAL')
        proposal=json.loads(record['proposal_json']);expected=proposal['request']
        if record['state']=='CLOSED_VERIFIED':
            return {'state':'CLOSED_VERIFIED','dispatchAllowed':False,'alreadyFinal':True}
        if not isinstance(order,dict):raise ValueError('NO_ORDER_EVIDENCE')
        if (order.get('clientOrderId')!=expected['newClientOrderId']
            or order.get('symbol')!=expected['symbol']
            or order.get('side')!=expected['side']
            or order.get('positionSide')!=expected['positionSide']
            or order.get('type')!='LIMIT'
            or order.get('reduceOnly') is not True
            or decimal(order.get('price'))!=decimal(expected['price'])
            or decimal(order.get('origQty'))!=decimal(expected['quantity'])
            or not order.get('orderId')):
            raise ValueError('ORDER_EVIDENCE_MISMATCH')
        oid=str(order['orderId'])
        if record['exchange_order_id'] is not None and record['exchange_order_id']!=oid:
            raise ValueError('EXCHANGE_ORDER_ID_CHANGED')
        side=expected['positionSide']
        qty=expected['quantity']
        # This shadow audit relies on the immutable proposal's actual fills and fees.
        # The caller cannot use this as proof that any real order was sent.
        entry=proposal.get('entryAudit')
        if not isinstance(entry,dict):raise ValueError('MISSING_ENTRY_FILL_AUDIT')
        # A LIMIT exit must never execute below its sell limit or above
        # its buy limit; suspicious fills invalidate the shadow proof.
        limit=decimal(expected['price'])
        for fill in exit_fills:
            if not isinstance(fill,dict):raise ValueError('INVALID_EXIT_FILL')
            executed_price=decimal(fill.get('price'))
            if ((side=='LONG' and executed_price<limit)
                    or (side=='SHORT' and executed_price>limit)):
                raise ValueError('EXECUTION_WORSE_THAN_LIMIT')
        settlement=reconcile_fills(order_id=oid,side=side,entry_quantity=qty,
            entry_cost_usdt=entry['costUSDT'],entry_fees_usdt=entry['feesUSDT'],
            exit_fills=exit_fills,remaining_position_quantity=remaining_quantity)
        executed=decimal(order.get('executedQty'))
        if executed!=decimal(settlement['quantityClosed']):
            raise ValueError('ORDER_EXECUTED_QUANTITY_MISMATCH')
        status=order.get('status')
        if status not in ('NEW','PARTIALLY_FILLED','FILLED','CANCELED','EXPIRED','REJECTED'):
            raise ValueError('UNKNOWN_ORDER_STATUS')
        if status=='FILLED' and settlement['status']!='CLOSED_VERIFIED':
            raise ValueError('ORDER_FILLED_POSITION_NOT_CLOSED')
        if settlement['status']=='CLOSED_VERIFIED' and status!='FILLED':
            raise ValueError('CLOSE_WITHOUT_FILLED_ORDER')
        state=('CLOSED_VERIFIED' if settlement['status']=='CLOSED_VERIFIED'
               else 'REVIEW_REQUIRED' if status in ('CANCELED','EXPIRED','REJECTED')
               else settlement['status'])
        evidence={'orderId':oid,'orderStatus':status,'settlement':settlement}
        # Non-terminal observations must not reduce cumulative executed quantity.
        prev=json.loads(record['last_evidence_json']) if record['last_evidence_json'] else None
        if prev and decimal(prev['settlement']['quantityClosed'])>executed:
            raise ValueError('EXECUTION_HISTORY_REGRESSED')
        db.execute('UPDATE shadow_limit_v1 SET state=?,exchange_order_id=?,last_evidence_json=? WHERE trade_id=?',
                   (state,oid,canonical(evidence),trade_id))
        return {'state':state,'evidence':evidence,'dispatchAllowed':False}
