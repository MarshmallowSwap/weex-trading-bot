"""Read-only WEEX evidence for exact journal-bound pilot close orders.

No real orders, no account modifications, and no execution authorization.
An absent pilot stays UNVERIFIED; never infer a successful close from a flat account.
"""
import json,os,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
from weex_live_worker import Reader
from weex_pilot_close_proof_readonly import verify_close
import live_control

ROOT=Path(__file__).resolve().parent

def journal_rows(path):
    if not Path(path).is_file():return []
    with sqlite3.connect('file:'+Path(path).resolve().as_posix()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        names={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pilot_v1' not in names:raise ValueError('PILOT_SCHEMA_MISSING')
        return [dict(zip(('pilotId','side','quantity','closeId'),r)) for r in
                db.execute('SELECT pilot_id,side,quantity,close_id FROM pilot_v1')]

def evaluate(rows,positions,fetch_order,fetch_fills):
    result=[]
    for pilot in rows:
        cid=pilot['closeId']
        proof={'state':'UNVERIFIED','reason':'EXCHANGE_READ_FAILED',
               'canSend':False,'canRetry':False,'closeCertifiedForLive':False}
        try:
            order=fetch_order(cid)
            if not isinstance(order,dict) or order.get('clientOrderId')!=cid:
                proof['reason']='EXACT_CLIENT_ORDER_NOT_FOUND'
            else:
                oid=str(order.get('orderId') or '')
                if not oid:proof['reason']='MISSING_EXCHANGE_ORDER_ID'
                else:
                    fills=fetch_fills(order['symbol'],oid)
                    proof=verify_close(client_id=cid,side=pilot['side'],
                        quantity=pilot['quantity'],orders=[order],fills=fills,
                        positions=positions)
        except (ValueError,TypeError,KeyError):
            proof['reason']='EXCHANGE_OBSERVATION_INVALID'
        result.append({'pilotId':pilot['pilotId'],'closeClientId':cid,**proof})
    return {'pilotsChecked':len(rows),'closures':result,'allClosuresObservedUnattested':
            bool(result) and all(r['state']=='CONSISTENT_OBSERVATIONS_UNATTESTED' for r in result),
            'liveCloseCertified':False,'canSend':False,'canRetry':False,'exchangeWrites':0}

def run():
    if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('MAIN_BOT_NOT_STOPPED')
    rows=journal_rows(ROOT/'weex_isolated_pilot.sqlite3')
    if not rows:
        out=evaluate([],[],lambda _:None,lambda _s,_o:None)
    else:
        positions,regular,algos=Reader(ROOT).account()
        if not all(isinstance(x,list) for x in (positions,regular,algos)):
            raise ValueError('ACCOUNT_READ_INCOMPLETE')
        # WEEX direct order API is keyed by exchange orderId, not client ID.
        # Search a fully bounded history, then independently read back exact ID.
        from weex_order_pagination import history
        hist=history(max_pages=5)
        if not hist['completeWithinRequestedBounds']:
            raise ValueError('HISTORY_NOT_FULLY_PAGINATED')
        def fetch(cid):
            matches=[o for o in hist['orders'] if o.get('clientOrderId')==cid]
            if len(matches)!=1:return None
            oid=str(matches[0]['orderId'])
            order=query('/capi/v3/order?orderId='+oid)
            if not isinstance(order,dict) or str(order.get('orderId'))!=oid:
                raise ValueError('ORDER_READBACK_MISMATCH')
            return order
        def fills(symbol,oid):
            r=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
            if not isinstance(r,list) or len(r)>=100:raise ValueError('FILL_PAGE_INCOMPLETE')
            return r
        out=evaluate(rows,positions,fetch,fills)
    out.update(checkedAt=datetime.now(timezone.utc).isoformat(),
               source='EXACT_AUTHENTICATED_WEEX_GET_OR_EMPTY_JOURNAL',
               mainLiveMode='STOPPED')
    path=ROOT/'weex_pilot_emergency_close_readonly_latest.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,path)
    return out

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
