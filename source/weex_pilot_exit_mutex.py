"""One durable mutual exclusion gate for *all* pilot exit paths.

Legacy modules own their independent dispatch journal; this gate makes an exit
claim before invoking either one. Any crash leaves CLAIMED_UNKNOWN and prohibits
another potentially duplicative close. Only independently reconciled exchange
evidence may resolve the claim; never mark success on an SDK acknowledgement.
"""
import sqlite3
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect

EXITS=('reduce_only','position_id')

def claim(db,pilot_id,method):
    if method not in EXITS:raise ValueError('UNKNOWN_EXIT_METHOD')
    with closing(connect(db)) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS pilot_exit_mutex_v1(
          pilot_id TEXT PRIMARY KEY,method TEXT NOT NULL,state TEXT NOT NULL)''')
        c.execute('BEGIN IMMEDIATE')
        p=c.execute('SELECT state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if p is None:
            c.rollback();raise ValueError('UNKNOWN_PILOT')
        if p[0] not in ('ENTRY_RECONCILED_EXTERNALLY','STOP_RECONCILED_EXTERNALLY'):
            c.rollback();raise PermissionError('ENTRY_NOT_RECONCILED')
        prior=c.execute('SELECT method,state FROM pilot_exit_mutex_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if prior:
            c.rollback()
            return {'claimed':False,'reason':'EXISTING_EXIT_CLAIM','method':prior[0],
                    'state':prior[1],'canRetry':False}
        names={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('pilot_close_dispatch_v1','pilot_emergency_dispatch_v1'):
            if table in names and c.execute('SELECT 1 FROM '+table+' WHERE pilot_id=?',(pilot_id,)).fetchone():
                c.rollback()
                return {'claimed':False,'reason':'LEGACY_EXIT_ALREADY_RESERVED','canRetry':False}
        c.execute('INSERT INTO pilot_exit_mutex_v1 VALUES(?,?,?)',
                  (pilot_id,method,'CLAIMED_UNKNOWN'))
        c.commit()
        return {'claimed':True,'method':method,'state':'CLAIMED_UNKNOWN','canRetry':False}

def dispatch_exit(db,pilot_id,method,send_callback):
    result=claim(db,pilot_id,method)
    if not result['claimed']:return result
    try:
        response=send_callback()
    except Exception:
        return {**result,'outcome':'UNKNOWN','exchangeCloseVerified':False}
    return {**result,'outcome':'ACK_ONLY_UNVERIFIED','exchangeCloseVerified':False,
            'dispatchResult':response}
