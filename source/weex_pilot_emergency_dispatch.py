"""Durable at-most-once emergency close for an attested pilot position.

This operation may ONLY target one WEEX positionId, never a whole symbol/account.
UNKNOWN is never retried. Exchange GET readback must verify the eventual result.
"""
import json
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_emergency_close_sdk import exact_payload,OP

def dispatch(db,pilot_id,*,ownership,observed_position,transport,main_mode='STOPPED'):
    if main_mode!='STOPPED':raise PermissionError('MAIN_BOT_MUST_BE_STOPPED')
    if transport is None or getattr(transport,'pilot_emergency_close_only',False) is not True:
        raise PermissionError('REVIEWED_EMERGENCY_TRANSPORT_REQUIRED')
    if not isinstance(ownership,dict) or ownership.get('owned') is not True:
        raise PermissionError('INDEPENDENT_OWNERSHIP_REQUIRED')
    if not isinstance(observed_position,dict):
        raise PermissionError('FRESH_POSITION_REQUIRED')
    if (observed_position.get('symbol')!='ETHUSDT'
        or str(observed_position.get('id'))!=str(ownership.get('positionId'))
        or observed_position.get('marginType') not in ('ISOLATED','ISOLATE')
        or observed_position.get('side') not in ('LONG','SHORT')
        or str(observed_position.get('size'))!=str(ownership.get('quantity'))):
        raise PermissionError('POSITION_NOT_EXACT_PILOT')
    payload=exact_payload(ownership.get('positionId'))
    with closing(connect(db)) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS pilot_emergency_dispatch_v1(
             pilot_id TEXT PRIMARY KEY,position_id TEXT UNIQUE NOT NULL,
             state TEXT NOT NULL, response TEXT)''')
        c.execute('BEGIN IMMEDIATE')
        pilot=c.execute('SELECT entry_id,side,quantity,state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if pilot is None:
            c.rollback();raise ValueError('UNKNOWN_PILOT')
        previous=c.execute('SELECT state FROM pilot_emergency_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if previous:
            c.rollback();return {'state':'NO_RETRY_ALREADY_RESERVED','previous':previous[0],'canRetry':False}
        entry_id,side,quantity,state=pilot
        if (state!='ENTRY_RECONCILED_EXTERNALLY'
            or ownership.get('clientOrderId')!=entry_id
            or str(ownership.get('quantity'))!=str(quantity)
            or observed_position['side']!=side):
            c.rollback();raise PermissionError('JOURNAL_OWNERSHIP_NOT_EXACT')
        # Atomic shared claim blocks concurrent ordinary reduceOnly exit.
        c.execute('''CREATE TABLE IF NOT EXISTS pilot_exit_mutex_v1(
            pilot_id TEXT PRIMARY KEY,method TEXT NOT NULL,state TEXT NOT NULL)''')
        if c.execute('SELECT 1 FROM pilot_exit_mutex_v1 WHERE pilot_id=?',(pilot_id,)).fetchone():
            c.rollback();raise PermissionError('ANOTHER_EXIT_ALREADY_RESERVED')
        if ('pilot_close_dispatch_v1' in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            and c.execute('SELECT 1 FROM pilot_close_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()):
            c.rollback();raise PermissionError('REDUCE_ONLY_EXIT_ALREADY_RESERVED')
        c.execute('INSERT INTO pilot_exit_mutex_v1 VALUES(?,?,?)',
                  (pilot_id,'position_id','CLAIMED_UNKNOWN'))
        # Durable reservation first. A crash creates UNKNOWN, never a resend.
        c.execute('INSERT INTO pilot_emergency_dispatch_v1 VALUES(?,?,?,NULL)',
                  (pilot_id,str(payload['positionId']),'OUTCOME_UNKNOWN'))
        c.commit()
    try:
        result=transport.send_emergency_close(OP,payload)
    except Exception:
        return {'state':'OUTCOME_UNKNOWN','canRetry':False,'verifiedFlat':False}
    if not isinstance(result,dict) or result.get('success') is not True or not result.get('orderId'):
        return {'state':'OUTCOME_UNKNOWN','canRetry':False,'verifiedFlat':False}
    with closing(connect(db)) as c:
        with c:
            c.execute('UPDATE pilot_emergency_dispatch_v1 SET state=?,response=? WHERE pilot_id=?',
                      ('ACK_RECEIVED_NEEDS_EXCHANGE_READBACK',
                       json.dumps({'orderId':str(result['orderId'])}),pilot_id))
    return {'state':'ACK_RECEIVED_NEEDS_EXCHANGE_READBACK','canRetry':False,'verifiedFlat':False}
