"""Fail-closed durable TP repair state transitions.

No exchange write is performed here. The dispatcher may use these transitions
only while holding the shared WEEX cycle lock; UNKNOWN never permits retries.
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from weex_lifecycle import now

def _path(root):
    return Path(root)/'weex_user_tp_repair_proposals.sqlite3'

def mark_dispatch_unknown(root, trade_id, *, expected_digest):
    """Atomically mark an immutable intent UNKNOWN before any network I/O."""
    with closing(sqlite3.connect(_path(root),timeout=10)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT state,payload_sha256 FROM dispatch_intents_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        if not row or row[1]!=expected_digest:
            raise PermissionError('INTENT_IDENTITY_MISMATCH')
        if row[0]!='PREPARED_NOT_SENT':
            db.commit()
            return {'state':'NO_RETRY','dispatchAllowed':False}
        db.execute("UPDATE dispatch_intents_v1 SET state='UNKNOWN' WHERE trade_id=?",(trade_id,))
        db.commit()
    return {'state':'UNKNOWN','dispatchAllowed':False}

def reconcile(root, trade_id, observations, *, position_id, client_algo_id):
    """Accept VERIFIED only with complete fresh position, order, and history evidence."""
    with closing(sqlite3.connect(_path(root),timeout=10)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT state,position_id,payload,exchange_order_id FROM dispatch_intents_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        if not row:
            raise ValueError('INTENT_NOT_FOUND')
        state,pid,raw,exchange_id=row
        import json
        request=json.loads(raw)
        if state not in ('UNKNOWN','VERIFIED'):
            return {'state':'NOT_DISPATCHED','dispatchAllowed':False}
        if pid!=str(position_id) or client_algo_id!=request.get('clientAlgoId'):
            return {'state':'REVIEW_IDENTITY_CHANGED','dispatchAllowed':False}
        if not isinstance(observations,dict) or observations.get('complete') is not True:
            return {'state':'RECONCILIATION_REQUIRED','dispatchAllowed':False}
        positions=observations.get('positions')
        regular=observations.get('regularOrders')
        algos=observations.get('conditionalOrders')
        if not all(isinstance(x,list) for x in (positions,regular,algos)):
            return {'state':'RECONCILIATION_REQUIRED','dispatchAllowed':False}
        own=[p for p in positions if str(p.get('id'))==pid and p.get('symbol')==request['symbol']]
        matching=[o for o in algos if o.get('clientAlgoId')==client_algo_id]
        if len(own)!=1 or len(matching)!=1 or any(o.get('symbol')==request['symbol'] for o in regular):
            return {'state':'REVIEW_AMBIGUOUS_EXPOSURE','dispatchAllowed':False}
        p=own[0];a=matching[0]
        from decimal import Decimal
        from weex_capacity import full_closing_tp
        if (p.get('side')!=request['positionSide']
                or Decimal(str(p.get('size')))!=Decimal(str(request['quantity']))
                or a.get('algoStatus') not in ('NEW','UNTRIGGERED')
                or not full_closing_tp(a,own)
                or not a.get('algoId')
                or (exchange_id is not None and str(exchange_id)!=str(a['algoId']))):
            return {'state':'REVIEW_TP_NOT_VERIFIED','dispatchAllowed':False}
        if state=='VERIFIED':
            return {'state':'VERIFIED','dispatchAllowed':False}
        db.execute("UPDATE dispatch_intents_v1 SET state='VERIFIED',exchange_order_id=? WHERE trade_id=?",
                   (str(a['algoId']),trade_id))
        db.commit()
    return {'state':'VERIFIED','dispatchAllowed':False}
