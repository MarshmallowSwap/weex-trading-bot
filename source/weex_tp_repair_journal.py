"""WEEX TP recovery proposal journal. Does not submit exchange orders."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from weex_lifecycle import dump, now

def record(root, proposal):
    if proposal.get('eligible') is not True or proposal.get('dispatchAllowed') is not False:
        raise ValueError('PROPOSAL_NOT_FAIL_CLOSED')
    tid = proposal['tradeId']
    symbol = proposal['symbol']
    position = proposal['positionId']
    if not all(isinstance(x,str) and x for x in (tid,symbol,position)):
        raise ValueError('INVALID_PROPOSAL_IDENTITY')
    fingerprint = hashlib.sha256(dump({
        'tradeId':tid,'symbol':symbol,'positionId':position,'reason':proposal['reason']
    }).encode()).hexdigest()
    path = Path(root)/'weex_user_tp_repair_proposals.sqlite3'
    with closing(sqlite3.connect(path,timeout=5)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        db.execute("""CREATE TABLE IF NOT EXISTS proposals_v1(
            trade_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,position_id TEXT NOT NULL,
            fingerprint TEXT NOT NULL,state TEXT NOT NULL,created INTEGER NOT NULL)""")
        prior = db.execute('SELECT fingerprint,state FROM proposals_v1 WHERE trade_id=?',(tid,)).fetchone()
        if prior:
            db.commit()
            if prior[0] != fingerprint:
                return {'state':'REVIEW_PROPOSAL_CHANGED','tradeId':tid,'dispatchAllowed':False}
            return {'state':'ALREADY_PROPOSED','tradeId':tid,'dispatchAllowed':False}
        db.execute("INSERT INTO proposals_v1 VALUES(?,?,?,?,?,?)",
                   (tid,symbol,position,fingerprint,'PROPOSAL_ONLY',now()))
        db.commit()
    return {'state':'PROPOSED','tradeId':tid,'dispatchAllowed':False}
