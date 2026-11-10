"""Pilot-only verified close dispatch with durable no-retry semantics.

No standalone internet client or credentials. The transport callback is supplied
by an externally reviewed live adapter, which must enforce the pilot's explicit
permissions and authenticate the exact SDK request. This module never authorizes
an entry, nor infers ownership from a client-provided manualOrMixed flag.
"""
import json,sqlite3
from contextlib import closing
from pathlib import Path
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_one_shot_exit import validated_close_payload
from weex_http_guard import prepare_sdk_request

def ensure_schema(c):
    c.execute("""CREATE TABLE IF NOT EXISTS pilot_close_dispatch_v1 (
        pilot_id TEXT PRIMARY KEY, close_client_id TEXT NOT NULL UNIQUE,
        state TEXT NOT NULL, payload TEXT NOT NULL, response TEXT)""")

def dispatch_close(db, pilot_id, proposal, *, ownership, account_fresh, transport, main_mode='STOPPED'):
    if main_mode!='STOPPED':
        raise PermissionError('PRODUCTION_BOT_MUST_BE_STOPPED')
    if transport is None or getattr(transport,'pilot_live_close_only',False) is not True:
        raise PermissionError('REVIEWED_CLOSE_TRANSPORT_REQUIRED')
    if account_fresh is not True or not isinstance(ownership,dict) or ownership.get('owned') is not True:
        raise PermissionError('OWNERSHIP_AND_FRESH_ACCOUNT_REQUIRED')
    if not isinstance(proposal,dict) or proposal.get('prepared') is not True or proposal.get('canSend') is not False:
        raise PermissionError('VERIFIED_OFFLINE_CLOSE_PLAN_REQUIRED')
    payload=validated_close_payload(proposal.get('payload'))
    preview=prepare_sdk_request('post_capi_v3_order',payload)
    if preview.get('state')!='STOPPED_BEFORE_NETWORK' or preview.get('networkRequests')!=0:
        raise PermissionError('EXACT_SDK_PREVIEW_FAILED')
    with closing(connect(db)) as c:
        ensure_schema(c)
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT side,quantity,entry_id,close_id,state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if not row:
            c.rollback();raise ValueError('UNKNOWN_PILOT')
        side,qty,entry_id,close_id,state=row
        prior=c.execute('SELECT state FROM pilot_close_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if prior:
            c.rollback()
            return {'state':'ALREADY_RESERVED_NO_RETRY','prior':prior[0],'ordersConfirmed':False}
        if (state not in ('ENTRY_RECONCILED_EXTERNALLY','STOP_RECONCILED_EXTERNALLY')
            or close_id!=payload['newClientOrderId']
            or entry_id!=ownership.get('clientOrderId')
            or ownership.get('quantity')!=str(qty)
            or ownership.get('positionId') in (None,'')
            or payload['positionSide']!=side or payload['quantity']!=str(qty)):
            c.rollback();raise PermissionError('CLOSE_NOT_BOUND_TO_JOURNALED_OWNED_PILOT')
        # Shared atomic exit reservation also blocks emergency positionId close.
        c.execute('''CREATE TABLE IF NOT EXISTS pilot_exit_mutex_v1(
            pilot_id TEXT PRIMARY KEY,method TEXT NOT NULL,state TEXT NOT NULL)''')
        if c.execute('SELECT 1 FROM pilot_exit_mutex_v1 WHERE pilot_id=?',(pilot_id,)).fetchone():
            c.rollback();raise PermissionError('ANOTHER_EXIT_ALREADY_RESERVED')
        if ('pilot_emergency_dispatch_v1' in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            and c.execute('SELECT 1 FROM pilot_emergency_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()):
            c.rollback();raise PermissionError('EMERGENCY_EXIT_ALREADY_RESERVED')
        c.execute('INSERT INTO pilot_exit_mutex_v1 VALUES (?,?,?)',
                  (pilot_id,'reduce_only','CLAIMED_UNKNOWN'))
        # Persist UNKNOWN before external transmission. Never auto-repeat this ID.
        c.execute('INSERT INTO pilot_close_dispatch_v1 VALUES (?,?,?,?,NULL)',
                 (pilot_id,close_id,'OUTCOME_UNKNOWN',json.dumps(payload,sort_keys=True)))
        c.commit()
    try:
        acknowledgement=transport.send_close_only('post_capi_v3_order',payload)
    except Exception:
        return {'state':'OUTCOME_UNKNOWN','canRetry':False,'ordersConfirmed':False}
    if not isinstance(acknowledgement,dict) or acknowledgement.get('success') is not True or not acknowledgement.get('orderId'):
        return {'state':'OUTCOME_UNKNOWN','canRetry':False,'ordersConfirmed':False}
    with closing(connect(db)) as c:
        with c:
            c.execute('UPDATE pilot_close_dispatch_v1 SET state=?,response=? WHERE pilot_id=? AND state=?',
                      ('ACK_RECEIVED_UNRECONCILED',json.dumps({'orderId':str(acknowledgement['orderId'])}),
                       pilot_id,'OUTCOME_UNKNOWN'))
    return {'state':'ACK_RECEIVED_UNRECONCILED','canRetry':False,
            'ordersConfirmed':False,'requiresExactOrderAndFillReadback':True}
