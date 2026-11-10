"""Recover journaled pilot executions after restart via authenticated WEEX GET.

Never sends orders. Missing exchange evidence remains UNKNOWN and cannot be
retried automatically. Intended to run before any further pilot action.
"""
import json,os,sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime,timezone
from weex_live_worker import Reader
from weex_order_pagination import history
from monitor import query
from weex_pilot_dispatch_reconciliation import reconcile
from weex_pilot_emergency_reconciliation import reconcile_emergency
import live_control

ROOT=Path(__file__).resolve().parent

def pending(db):
    if not db.is_file():return []
    with closing(sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)) as c:
        c.execute('PRAGMA query_only=ON')
        names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        records=[]
        for stage,table in (('entry','pilot_entry_dispatch_v1'),('close','pilot_close_dispatch_v1')):
            if table not in names:continue
            records.extend((p,stage) for p,s in c.execute('SELECT pilot_id,state FROM '+table)
                           if s!='EXCHANGE_FILLED_RECONCILED')
        if 'pilot_emergency_dispatch_v1' in names:
            records.extend((p,'emergency') for p,s in c.execute(
                'SELECT pilot_id,state FROM pilot_emergency_dispatch_v1')
                if s!='EXCHANGE_FILLED_RECONCILED')
        return records

def run(root=ROOT):
    root=Path(root)
    if live_control.state(root)['mode']!='STOPPED':raise PermissionError('PRODUCTION_MUST_BE_STOPPED')
    if live_control.build_errors(root):raise PermissionError('INTEGRITY_FAILED')
    db=root/'weex_isolated_pilot.sqlite3'
    items=pending(db)
    results=[]
    if items:
        positions,regular,conditional=Reader(root).account()
        if any(not isinstance(x,list) for x in (positions,regular,conditional)):
            raise ValueError('WEEX_ACCOUNT_READ_INVALID')
        hist=history(max_pages=5)
        if hist.get('completeWithinRequestedBounds') is not True:
            raise ValueError('ORDER_HISTORY_INCOMPLETE')
        with sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True) as c:
            ids={p:(row[0],row[1]) for p,stage in items
                 for row in c.execute('SELECT entry_id,close_id FROM pilot_v1 WHERE pilot_id=?',(p,))}
        for pid,stage in items:
            if stage=='emergency':
                with sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True) as c:
                    row=c.execute('SELECT response FROM pilot_emergency_dispatch_v1 WHERE pilot_id=?',(pid,)).fetchone()
                response=json.loads(row[0]) if row and row[0] else {}
                oid=str(response.get('orderId') or '')
                order=None;fills=[]
                if oid:
                    order=query('/capi/v3/order?orderId='+oid)
                    if not isinstance(order,dict) or str(order.get('orderId'))!=oid:
                        raise ValueError('EMERGENCY_ORDER_READBACK_MISMATCH')
                    fills=query('/capi/v3/userTrades?symbol=ETHUSDT&orderId='+oid+'&limit=100')
                    if not isinstance(fills,list) or len(fills)>=100:
                        raise ValueError('EMERGENCY_FILL_PAGE_INCOMPLETE')
                r=reconcile_emergency(db,pid,order=order,fills=fills,
                                     positions=positions,regular=regular,conditional=conditional)
                results.append({'pilotId':pid,'stage':'emergency',**r})
                continue
            cid=ids[pid][0 if stage=='entry' else 1]
            candidates=[o for o in hist['orders'] if o.get('clientOrderId')==cid]
            order=None;fills=[]
            if len(candidates)==1 and candidates[0].get('orderId'):
                oid=str(candidates[0]['orderId'])
                order=query('/capi/v3/order?orderId='+oid)
                if not isinstance(order,dict) or str(order.get('orderId'))!=oid:
                    raise ValueError('ORDER_READBACK_MISMATCH')
                fills=query('/capi/v3/userTrades?symbol=ETHUSDT&orderId='+oid+'&limit=100')
                if not isinstance(fills,list) or len(fills)>=100:
                    raise ValueError('FILL_PAGE_NOT_COMPLETE')
            result=reconcile(db,pid,stage,order=order,fills=fills,positions=positions,
                              regular_orders=regular,conditional_orders=conditional)
            results.append({'pilotId':pid,'stage':stage,**result})
    result={'checkedAt':datetime.now(timezone.utc).isoformat(),
            'mode':'AUTHENTICATED_GET_ONLY_RECOVERY','pendingFound':len(items),
            'results':results,'ordersSent':0,'mainMode':'STOPPED'}
    out=root/'weex_pilot_dispatch_readback_latest.json'
    temp=out.with_suffix('.tmp')
    temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temp,out)
    return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
