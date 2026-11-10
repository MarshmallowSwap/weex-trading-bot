"""Unified exact-identity pilot lifecycle readback. Strictly GET-only.

Isolated from the main 125x strategy and from any write-capable transport.
Missing attribution must never result in a close proposal.
"""
import json,sqlite3,os
from pathlib import Path
from datetime import datetime,timezone
from weex_live_worker import Reader
from weex_order_pagination import history
from monitor import query
from weex_pilot_isolated_close_plan import plan
from weex_pilot_ownership_attestation import attest
from weex_pilot_baseline_load import load as load_baseline
from weex_pilot_one_shot_exit import validated_close_payload
from weex_http_guard import prepare_sdk_request
from weex_pilot_emergency_close_readonly import evaluate as close_evidence
import live_control

ROOT=Path(__file__).resolve().parent

def journals(path):
    path=Path(path)
    if not path.is_file():return []
    with sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pilot_v1' not in names:raise ValueError('PILOT_DB_SCHEMA_MISSING')
        return [dict(zip(('pilotId','side','quantity','entryId','closeId','state'),row)) for row in
                db.execute('SELECT pilot_id,side,quantity,entry_id,close_id,state FROM pilot_v1')]

def check(rows,positions,regular,algos,find_order,find_fills,baseline=None):
    audits=[]
    for p in rows:
        entry=find_order(p['entryId'])
        if (not isinstance(entry,dict) or entry.get('clientOrderId')!=p['entryId']
            or not entry.get('orderId') or entry.get('symbol')!='ETHUSDT'):
            audits.append({'pilotId':p['pilotId'],'state':'ENTRY_NOT_OBSERVED','closePrepared':False,
                           'canSend':False,'canRetry':False})
            continue
        try:
            fills=find_fills(entry['symbol'],str(entry['orderId']))
            # No synthetic owner flag: derive it only from authenticated
            # baseline + exact entry, fills and unique subsequent position.
            ownership=attest(baseline=baseline,position=positions[0] if len(positions)==1 else {},
                             entry=entry,fill_rows=fills,pilot=p)
            if ownership['owned'] is not True or positions[0].get('manualOrMixed') is True:
                reason=ownership['reason'] if ownership['owned'] is not True else 'MANUAL_OR_MIXED_POSITION'
                proposed={'prepared':False,'reason':'OWNERSHIP_NOT_ATTESTED:'+reason}
            else:
                attributed=[{**positions[0],'manualOrMixed':False}]
                proposed=plan(pilot=p,entry_order=entry,entry_fills=fills,
                              positions=attributed,regular_orders=regular,algos=algos,
                              observed_fresh=True)
                if proposed.get('prepared') is True:
                    payload=validated_close_payload(proposed['payload'])
                    proof=prepare_sdk_request('post_capi_v3_order',payload)
                    if (proof.get('state')!='STOPPED_BEFORE_NETWORK'
                        or proof.get('networkRequests')!=0):
                        proposed={'prepared':False,'reason':'CLOSE_SDK_SERIALIZATION_UNVERIFIED'}
        except (KeyError,TypeError,ValueError,ArithmeticError):
            proposed={'prepared':False,'reason':'EXCHANGE_EVIDENCE_UNAVAILABLE'}
        audits.append({'pilotId':p['pilotId'],'state':'ENTRY_OBSERVED_UNATTESTED',
                      'closePrepared':proposed.get('prepared') is True,
                      'closeReason':proposed.get('reason'),
                      'canSend':False,'canRetry':False})
    return {'pilots':len(rows),'audits':audits,'entryAuthorization':False,
            'exitAuthorization':False,'exchangeWrites':0}

def run():
    if live_control.state(ROOT)['mode']!='STOPPED':
        raise PermissionError('PRODUCTION_BOT_MUST_BE_STOPPED')
    rows=journals(ROOT/'weex_isolated_pilot.sqlite3')
    if not rows:
        result=check([],[],[],[],lambda _:None,lambda s,o:None)
    else:
        positions,regular,algos=Reader(ROOT).account()
        if not all(isinstance(v,list) for v in (positions,regular,algos)):
            raise ValueError('ACCOUNT_READ_INVALID')
        hist=history(max_pages=5)
        if not hist.get('completeWithinRequestedBounds'):
            raise ValueError('PAGINATION_INCOMPLETE')
        def order_by_client(cid):
            matched=[o for o in hist['orders'] if o.get('clientOrderId')==cid]
            if len(matched)!=1:return None
            oid=str(matched[0].get('orderId') or '')
            if not oid:return None
            order=query('/capi/v3/order?orderId='+oid)
            if not isinstance(order,dict) or str(order.get('orderId'))!=oid or order.get('clientOrderId')!=cid:
                raise ValueError('EXACT_ORDER_MISMATCH')
            return order
        def fills_by_id(symbol,oid):
            data=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
            if not isinstance(data,list) or len(data)>=100:
                raise ValueError('FILL_HISTORY_NOT_COMPLETE')
            return data
        baseline=load_baseline(ROOT/'weex_pilot_flat_baseline_latest.json')
        result=check(rows,positions,regular,algos,order_by_client,fills_by_id,baseline)
    result.update({'checkedAt':datetime.now(timezone.utc).isoformat(),
                   'mode':'READ_ONLY_PILOT_LIFECYCLE','productionMode':'STOPPED'})
    target=ROOT/'weex_pilot_unified_lifecycle_latest.json'
    temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temp,target)
    return result

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
