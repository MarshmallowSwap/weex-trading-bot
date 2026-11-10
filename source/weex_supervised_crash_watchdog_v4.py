"""Independent, read-only production-crash observation for the supervised ETH pilot.

Never submits an entry, close, cancel or TP. Has no live authorization path.
A missing/ambiguous/aged observation is a BLOCK, not a retry signal.
Runs as its own process and stores an atomic diagnostic on each invocation.
"""
from __future__ import annotations
import json,os,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone
from contextlib import closing

ROOT=Path(__file__).resolve().parent
REPORT='weex_supervised_crash_watchdog_latest.json'

def has_unknown_entry(root,client_id):
    db=Path(root)/'weex_user_live_lifecycle.sqlite3'
    if not db.is_file():
        return False
    with closing(sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)) as con:
        con.execute('PRAGMA query_only=ON')
        rows=con.execute(
          "SELECT state FROM writes_v1 WHERE trade_id=? AND kind='ENTRY'",(client_id,)).fetchall()
    if len(rows)>1:
        raise RuntimeError('AMBIGUOUS_ENTRY_JOURNAL')
    return len(rows)==1 and rows[0][0]=='UNKNOWN'

def decide(*,control_mode,integrity_ok,unknown_entry,verification=None,error=None):
    base={'safeToResubmitEntry':False,'authorizedToClose':False,
        'automatedEntryAllowed':False,'exchangeWrites':0}
    if control_mode!='STOPPED' or not integrity_ok:
        return {'status':'CRITICAL_CONTROL_OR_INTEGRITY',**base}
    if error:
        return {'status':'REVIEW_REQUIRED_READBACK_UNCERTAIN','reason':error,**base}
    if not unknown_entry:
        return {'status':'NO_UNKNOWN_PILOT_ENTRY','reason':'No journaled supervised crash to adopt',**base}
    if not isinstance(verification,dict):
        return {'status':'REVIEW_REQUIRED_EXCHANGE_UNVERIFIED',**base}
    if verification.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE':
        return {'status':'REVIEW_REQUIRED_ENTRY_OR_STOP_UNVERIFIED',**base}
    return {'status':'PROTECTED_EXACT_CLOSE_READY_FOR_SEPARATE_APPROVAL',
        'clientOrderId':verification.get('clientOrderId'),
        'positionId':verification.get('positionId'),
        'stopAlgoId':verification.get('stopAlgoId'),
        **base}

def observe(root=ROOT,*,checker=None,client_id=None):
    root=Path(root)
    from weex_supervised_crash_executor_v2 import CLIENT_ID
    from weex_supervised_real_recovery_v3 import read_exchange
    import live_control
    cid=client_id or CLIENT_ID
    mode=live_control.state(root)['mode']
    integrity=not live_control.build_errors(root)
    pending=False
    proof=None
    problem=None
    try:
        pending=has_unknown_entry(root,cid)
        if pending and mode=='STOPPED' and integrity:
            proof=(checker or read_exchange)(cid,root=root)
    except Exception as exc:
        # Signed URLs, API credentials or order details must not leak to reports.
        problem=type(exc).__name__
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),
        'mode':'INDEPENDENT_READ_ONLY_WATCHDOG',
        'scope':'ETHUSDT_100X_SUPERVISED_CRASH_V4',
        **decide(control_mode=mode,integrity_ok=integrity,
            unknown_entry=pending,verification=proof,error=problem)}
    target=root/REPORT
    tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(tmp,target)
    return report

if __name__=='__main__':
    # No argument permits an exchange write or an entry retry.
    print(json.dumps(observe(),ensure_ascii=False))
