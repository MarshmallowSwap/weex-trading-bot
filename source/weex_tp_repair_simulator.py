"""Offline replacement TP dispatch simulator.

Durable intent is written before the first possible transport call. The simulator
cannot access WEEX and is deliberately NOT imported by the live worker.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from weex_lifecycle import dump, now

def client_id(trade_id, position_id, attempt=1):
    if attempt != 1:
        raise ValueError('ONLY_ONE_REPLACEMENT_ATTEMPT_SUPPORTED')
    digest=hashlib.sha256((trade_id+'|'+position_id+'|tp-repair-v1').encode()).hexdigest()[:24]
    return 'wxr_'+digest

def prepare(root, proposal, request):
    if proposal.get('eligible') is not True or proposal.get('dispatchAllowed') is not False:
        raise ValueError('UNVERIFIED_PROPOSAL')
    trade_id=proposal['tradeId']
    position_id=proposal['positionId']
    if not all(isinstance(v,str) and v for v in (trade_id,position_id,proposal['symbol'])):
        raise ValueError('INVALID_IDENTITY')
    expected=client_id(trade_id,position_id)
    if (request.get('clientAlgoId')!=expected or request.get('symbol')!=proposal['symbol']
        or request.get('reduceOnly') is not True
        or request.get('positionSide') not in ('LONG','SHORT')
        or request.get('quantity') is None):
        raise ValueError('UNSAFE_REPLACEMENT_REQUEST')
    path=Path(root)/'weex_tp_repair_simulation.sqlite3'
    with closing(sqlite3.connect(path, timeout=5)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        db.execute("""CREATE TABLE IF NOT EXISTS simulated_dispatch_v1(
            trade_id TEXT PRIMARY KEY, client_id TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL, state TEXT NOT NULL,
            exchange_id TEXT, created INTEGER NOT NULL)""")
        row=db.execute('SELECT client_id,payload,state FROM simulated_dispatch_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        payload=dump(request)
        if row:
            db.commit()
            if row[0]!=expected or row[1]!=payload:
                raise ValueError('IMMUTABLE_INTENT_CONFLICT')
            return {'state':row[2],'clientAlgoId':expected,'dispatchAllowed':False}
        db.execute('INSERT INTO simulated_dispatch_v1 VALUES(?,?,?,?,NULL,?)',
                   (trade_id,expected,payload,'UNKNOWN',now()))
        db.commit()
    return {'state':'UNKNOWN','clientAlgoId':expected,'dispatchAllowed':False}

def reconcile(root, trade_id, observations):
    """Observations must come from a complete, authoritative simulated exchange."""
    path=Path(root)/'weex_tp_repair_simulation.sqlite3'
    with closing(sqlite3.connect(path,timeout=5)) as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT client_id,state,exchange_id FROM simulated_dispatch_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        if not row:
            raise ValueError('UNKNOWN_INTENT')
        client,state,exchange_id=row
        if not isinstance(observations,dict) or observations.get('complete') is not True:
            db.commit()
            return {'state':'UNKNOWN_RECONCILIATION_REQUIRED','dispatchAllowed':False}
        matched=[x for x in observations.get('orders',[]) if x.get('clientAlgoId')==client]
        if len(matched)!=1:
            db.commit()
            return {'state':'REVIEW_AMBIGUOUS_OR_MISSING','dispatchAllowed':False}
        order=matched[0]
        if not order.get('algoId') or order.get('algoStatus') not in ('NEW','UNTRIGGERED'):
            db.commit()
            return {'state':'REVIEW_NOT_ACTIVE','dispatchAllowed':False}
        if exchange_id and str(exchange_id)!=str(order['algoId']):
            db.commit()
            return {'state':'REVIEW_EXCHANGE_ID_CHANGED','dispatchAllowed':False}
        db.execute("UPDATE simulated_dispatch_v1 SET state='VERIFIED_SIMULATED',exchange_id=? WHERE trade_id=?",
                   (str(order['algoId']),trade_id))
        db.commit()
    return {'state':'VERIFIED_SIMULATED','dispatchAllowed':False}

def simulate_dispatch(root, trade_id, fake_transport):
    """One-shot injected fake transport; never WEEX. Unknown results are not resent."""
    path=Path(root)/'weex_tp_repair_simulation.sqlite3'
    with closing(sqlite3.connect(path,timeout=5)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT payload,state FROM simulated_dispatch_v1 WHERE trade_id=?',(trade_id,)).fetchone()
        if row is None:
            db.rollback()
            raise ValueError('INTENT_NOT_PREPARED')
        if row[1]!='UNKNOWN':
            db.commit()
            return {'state':'RECONCILE_NO_RETRY','dispatchAllowed':False}
        db.execute("UPDATE simulated_dispatch_v1 SET state='SIMULATED_DISPATCH_STARTED' WHERE trade_id=?",(trade_id,))
        db.commit()
    try:
        # Injection restricted to a caller-supplied local fake. No SDK imports.
        fake_transport(json.loads(row[0]))
    except Exception:
        return {'state':'SIMULATED_RESPONSE_UNKNOWN','dispatchAllowed':False}
    return {'state':'SIMULATED_RESPONSE_RECEIVED_RECONCILE_REQUIRED','dispatchAllowed':False}
