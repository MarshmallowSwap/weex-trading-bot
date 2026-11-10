"""Bounded WEEX trade collector: up to 1000 rows, millisecond boundary-proof.

The endpoint has limit=100 and no page parameter. Each full window is
followed by an exact-timestamp boundary query, which must return <100 rows.
Never silently drop fills sharing the oldest millisecond. Fail closed.
"""
from monitor import query
import json,os
from pathlib import Path

def collect(target=1000,fetch=query,max_batches=24,checkpoint_path=None):
    if type(target) is not int or not 1<=target<=1000:raise ValueError('MAX_1000')
    if type(max_batches) is not int or not 1<=max_batches<=40:raise ValueError('MAX_BATCHES')
    rows={};end=None;calls=0;complete=False;failure=None;boundaries=0
    cp=Path(checkpoint_path) if checkpoint_path is not None else None
    if cp and cp.exists():
        saved=json.loads(cp.read_text(encoding='utf-8'))
        if saved.get('target')!=target:raise ValueError('CHECKPOINT_SCOPE_MISMATCH')
        rows=saved['rows'];end=saved['nextEnd'];boundaries=saved['boundaryProofs']
        if len(rows)>target+100:raise ValueError('CHECKPOINT_ROWS_EXCEED_SAFE_BOUND')
    def save_checkpoint():
        if cp is None:return
        data={'target':target,'rows':rows,'nextEnd':end,'boundaryProofs':boundaries}
        temp=cp.with_suffix('.tmp');temp.write_text(json.dumps(data),encoding='utf-8')
        os.replace(temp,cp)
    def insert(batch):
        for row in batch:
            if (not isinstance(row,dict) or not row.get('id')
                or not row.get('orderId') or not row.get('symbol')
                or type(row.get('time')) not in (int,float,str)):
                raise ValueError('TRADE_IDENTITY_INVALID')
            stamp=int(row['time'])
            if stamp<=0:raise ValueError('TRADE_TIME_INVALID')
            key=str(row['id'])
            if key in rows and rows[key]!=row:
                raise ValueError('CONFLICTING_TRADE_DUPLICATE')
            rows[key]=row
    while len(rows)<target and calls<max_batches:
        limit=100
        path='/capi/v3/userTrades?limit=100'
        if end is not None:path+='&endTime='+str(end)
        try:
            batch=fetch(path);calls+=1
            if not isinstance(batch,list) or len(batch)>100:raise ValueError('BAD_TRADE_PAGE')
            if not batch:complete=True;break
            insert(batch)
            if len(batch)<100:complete=True;break
            oldest=min(int(x['time']) for x in batch)
            if end is not None and oldest>end:raise ValueError('TRADE_CURSOR_NOT_ADVANCING')
            # Check *all* fills at the inclusive boundary timestamp.
            # This proves that no timestamp collision is skipped.
            if calls>=max_batches:
                failure='BOUNDARY_PROOF_BUDGET_EXHAUSTED';break
            exact=fetch('/capi/v3/userTrades?limit=100&startTime='+str(oldest)+'&endTime='+str(oldest))
            calls+=1;boundaries+=1
            if not isinstance(exact,list) or len(exact)>=100:
                raise ValueError('TIMESTAMP_BOUNDARY_TOO_LARGE_OR_INVALID')
            if any(int(x['time'])!=oldest for x in exact):
                raise ValueError('EXCHANGE_IGNORED_TIMESTAMP_FILTER')
            page_ids={str(x['id']) for x in batch if int(x['time'])==oldest}
            boundary_ids={str(x['id']) for x in exact}
            if not page_ids.issubset(boundary_ids):
                raise ValueError('BOUNDARY_IDS_NOT_RECOVERED')
            insert(exact)
            end=oldest-1
            save_checkpoint()
        except Exception as exc:
            failure=type(exc).__name__ if type(exc).__name__!='ValueError' else str(exc)
            break
    ordered=sorted(rows.values(),key=lambda x:(-int(x['time']),str(x['id'])))
    # If an inclusive millisecond has more than the remaining target,
    # keeping a bounded subset is allowed but full chronological coverage
    # is not asserted.
    limited=ordered[:target]
    return {'trades':limited,'tradeCount':len(limited),'requestedTarget':target,
        'pagesFetched':calls,'boundaryProofs':boundaries,
        'historyExhaustedWithinBounds':complete,
        'reachedTarget':len(limited)>=target,'paginationFailure':failure,
        'scope':'AT_MOST_1000_RECENT_TRADES',
        'canCertifyCoverage':failure is None and (complete or len(limited)>=target),
        'exchangeWrites':False}
