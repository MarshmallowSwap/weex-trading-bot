"""Durable, immutable TP replacement intent; no direct WEEX execution.

The UNKNOWN state means dispatch might occur or may already have occurred.
Never retry UNKNOWN by itself. The caller must reconcile exchange history.
"""
import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from weex_lifecycle import dump, now
from weex_tp_repair_request import build

def prepare(root, proposal, trade):
    preview=build(proposal,trade)
    tid=trade['id']
    path=Path(root)/'weex_user_tp_repair_proposals.sqlite3'
    payload=dump(preview['request'])
    digest=hashlib.sha256((preview['operation']+'|'+payload).encode()).hexdigest()
    with closing(sqlite3.connect(path,timeout=10)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        db.execute("""CREATE TABLE IF NOT EXISTS dispatch_intents_v1(
            trade_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, position_id TEXT NOT NULL,
            operation TEXT NOT NULL, payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
            state TEXT NOT NULL, exchange_order_id TEXT, created_ms INTEGER NOT NULL)""")
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='proposals_v1'").fetchone()
        if not exists:
            raise ValueError('PERSISTED_PROPOSAL_REQUIRED')
        proposal_row=db.execute("SELECT position_id,fingerprint,state FROM proposals_v1 WHERE trade_id=?",(tid,)).fetchone()
        if (not proposal_row or proposal_row[0]!=str(proposal['positionId'])
                or proposal_row[2]!='PROPOSAL_ONLY'):
            raise ValueError('PERSISTED_PROPOSAL_REQUIRED')
        row=db.execute('SELECT operation,payload,payload_sha256,state FROM dispatch_intents_v1 WHERE trade_id=?',(tid,)).fetchone()
        if row:
            db.commit()
            if row[:3]!=(preview['operation'],payload,digest):
                raise ValueError('IMMUTABLE_REPAIR_INTENT_CONFLICT')
            return {'state':row[3],'tradeId':tid,'payloadSha256':digest,'dispatchAllowed':False}
        db.execute("INSERT INTO dispatch_intents_v1 VALUES(?,?,?,?,?,?,?,?,?)",
                   (tid,trade['symbol'],str(proposal['positionId']),preview['operation'],payload,
                    digest,'PREPARED_NOT_SENT',None,now()))
        db.commit()
    return {'state':'PREPARED_NOT_SENT','tradeId':tid,'payloadSha256':digest,
            'dispatchAllowed':False,'networkRequests':0}

def get(root,tid):
    path=Path(root)/'weex_user_tp_repair_proposals.sqlite3'
    with closing(sqlite3.connect(f'file:{path.resolve().as_posix()}?mode=ro',uri=True)) as db:
        row=db.execute('SELECT state,operation,payload_sha256,exchange_order_id FROM dispatch_intents_v1 WHERE trade_id=?',(tid,)).fetchone()
    if row is None:raise ValueError('INTENT_NOT_FOUND')
    return {'state':row[0],'operation':row[1],'payloadSha256':row[2],
            'exchangeOrderId':row[3],'dispatchAllowed':False}
