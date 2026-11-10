"""Safely void an unapproved WEEX pilot reservation before any dispatch.

Never delete a pilot if any dispatch table contains it, or if its state has
advanced beyond PREPARED_NO_SEND. This is not a reset of a sent order.
"""
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect

DISPATCH_TABLES=('pilot_entry_dispatch_v1','pilot_close_dispatch_v1',
                 'pilot_emergency_dispatch_v1','pilot_exit_mutex_v1')

def void_unapproved(db,pilot_id):
    with closing(connect(db)) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if row is None:
            c.rollback();return {'voided':False,'reason':'NO_RESERVATION'}
        if row[0]!='PREPARED_NO_SEND':
            c.rollback();return {'voided':False,'reason':'PILOT_ADVANCED'}
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in DISPATCH_TABLES:
            if table in tables and c.execute(
                    'SELECT 1 FROM '+table+' WHERE pilot_id=?',(pilot_id,)).fetchone():
                c.rollback()
                return {'voided':False,'reason':'DISPATCH_MAY_HAVE_OCCURRED'}
        c.execute('DELETE FROM pilot_v1 WHERE pilot_id=? AND state=?',
                  (pilot_id,'PREPARED_NO_SEND'))
        if c.total_changes!=1:
            c.rollback();return {'voided':False,'reason':'RACE_DETECTED'}
        c.commit()
        return {'voided':True,'reason':'NO_SEND_RESERVATION_VOIDED'}
