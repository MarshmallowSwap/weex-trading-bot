"""At-most-once pilot entry with durable UNKNOWN before network dispatch."""
import json
from decimal import Decimal
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_protected_entry_sdk import validate_protected,ProtectedEntryTransport
from weex_pilot_entry_sdk_adapter import validate_entry
from weex_http_guard import prepare_sdk_request

def send_entry_once(db,pilot_id,*,ask,account,transport,main_mode='STOPPED'):
    if main_mode!='STOPPED':raise PermissionError('PRODUCTION_MUST_BE_STOPPED')
    if transport is None or getattr(transport,'pilot_live_entry_only',False) is not True:
        raise PermissionError('PILOT_SDK_ENTRY_TRANSPORT_REQUIRED')
    with closing(connect(db)) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS pilot_entry_dispatch_v1(
            pilot_id TEXT PRIMARY KEY, client_id TEXT UNIQUE NOT NULL,
            state TEXT NOT NULL, response TEXT)""")
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT state,entry_id,proposals FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if not row:
            c.rollback();raise ValueError('UNKNOWN_PILOT')
        prior=c.execute('SELECT state FROM pilot_entry_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if prior:
            c.rollback()
            return {'state':'ALREADY_RESERVED_NO_RETRY','previous':prior[0],'canRetry':False}
        state,cid,raw=row
        if state!='PREPARED_NO_SEND':
            c.rollback();raise PermissionError('PILOT_NOT_PREPARED')
        candidate=json.loads(raw)['entry']
        payload=(validate_protected(candidate,ask)
                 if isinstance(transport,ProtectedEntryTransport)
                 else validate_entry(candidate,ask))
        if cid!=payload['newClientOrderId']:
            c.rollback();raise PermissionError('PILOT_ENTRY_ID_MISMATCH')
        if not callable(getattr(transport,'preflight_entry',None)):
            c.rollback();raise PermissionError('ENTRY_PREFLIGHT_REQUIRED')
        transport.preflight_entry('post_capi_v3_order',payload,ask=ask,account=account)
        preview=prepare_sdk_request('post_capi_v3_order',payload)
        if preview['networkRequests']!=0 or preview['state']!='STOPPED_BEFORE_NETWORK':
            c.rollback();raise PermissionError('SDK_ENTRY_PREVIEW_FAILED')
        # The first time a gateway is invoked, reserve an irrevocable no-retry
        # attempt even if the OS crashes before it receives any response.
        c.execute('INSERT INTO pilot_entry_dispatch_v1 VALUES(?,?,?,NULL)',
                  (pilot_id,cid,'OUTCOME_UNKNOWN'))
        c.commit()
    try:
        ack=transport.send_entry_only('post_capi_v3_order',payload,ask=ask,account=account)
    except Exception:
        return {'state':'OUTCOME_UNKNOWN','canRetry':False,'entryConfirmed':False}
    if not isinstance(ack,dict) or ack.get('success') is not True or not ack.get('orderId'):
        return {'state':'OUTCOME_UNKNOWN','canRetry':False,'entryConfirmed':False}
    with closing(connect(db)) as c:
        with c:
            c.execute('UPDATE pilot_entry_dispatch_v1 SET state=?,response=? WHERE pilot_id=? AND state=?',
                      ('ACK_RECEIVED_UNRECONCILED',json.dumps({'orderId':str(ack['orderId'])}),
                       pilot_id,'OUTCOME_UNKNOWN'))
    return {'state':'ACK_RECEIVED_UNRECONCILED','canRetry':False,
            'entryConfirmed':False,'requiresExactOrderAndFillReadback':True}
