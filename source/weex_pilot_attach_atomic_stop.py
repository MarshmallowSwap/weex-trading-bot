"""Atomically replace an OFFLINE reserved pilot entry with SDK bracket stop.

Do not modify any dispatch when its outcome may be unknown.
"""
import json
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_protected_entry_sdk import validate_protected
from weex_http_guard import prepare_sdk_request

def attach(db,pilot_id,*,stop,reference_price):
    with closing(connect(db)) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT state,entry_id,proposals FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if row is None or row[0]!='PREPARED_NO_SEND':
            c.rollback();raise PermissionError('PILOT_NOT_OFFLINE_PREPARED')
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('pilot_entry_dispatch_v1','pilot_close_dispatch_v1',
                      'pilot_emergency_dispatch_v1','pilot_exit_mutex_v1'):
            if table in tables and c.execute('SELECT 1 FROM '+table+' WHERE pilot_id=?',(pilot_id,)).fetchone():
                c.rollback();raise PermissionError('PILOT_ALREADY_DISPATCHED')
        proposals=json.loads(row[2])
        entry=proposals['entry']
        if entry['newClientOrderId']!=row[1] or 'slTriggerPrice' in entry:
            c.rollback();raise PermissionError('PILOT_ENTRY_ALREADY_CHANGED')
        entry['slTriggerPrice']=str(stop)
        entry['SlWorkingType']='MARK_PRICE'
        validate_protected(entry,reference_price)
        proof=prepare_sdk_request('post_capi_v3_order',entry)
        if proof['networkRequests']!=0 or proof['state']!='STOPPED_BEFORE_NETWORK':
            c.rollback();raise PermissionError('STOP_PAYLOAD_SDK_UNVERIFIED')
        c.execute('UPDATE pilot_v1 SET proposals=? WHERE pilot_id=? AND state=?',
                  (json.dumps(proposals),pilot_id,'PREPARED_NO_SEND'))
        c.commit()
        return entry
