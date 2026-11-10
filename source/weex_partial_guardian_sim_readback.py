"""Authenticated WEEX SIM V3 snapshot adapter, strictly GET-only.

Provides fresh positions/open-algos/open-orders to the durable Guardian.
No API writes, no LIVE fallback, no credentials in outputs. An HTTP 200
alone is never sufficient: all three responses must be complete lists.
The snapshot is invalid on timeout, pagination, or ambiguous identifiers.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from urllib.parse import urlsplit
from weex_sim_v3_auth_readonly import CREDENTIALS,readiness
from weex_sim_v3_guard import assess,SIM_HOST
HOST='https://'+SIM_HOST
PATHS={
 'positions':'/capi/v3/account/position/allPosition',
 'algos':'/capi/v3/openAlgoOrders',
 'regular_orders':'/capi/v3/openOrders'}
class SnapshotFailure(Exception):pass

def snapshot(*,transport=None,credentials_path=CREDENTIALS):
    if readiness(credentials_path).get('status')!='READY_FOR_READ_ONLY_AUTH_CHECK':
        raise SnapshotFailure('SIM_CREDENTIALS_NOT_READY')
    c=json.loads(credentials_path.read_text(encoding='utf-8'))
    opener=transport or urllib.request.urlopen
    result={}
    for label,path in PATHS.items():
        url=HOST+path
        if assess('GET',url).get('allowed') is not True:raise SnapshotFailure('READ_FIREWALL_DENIED')
        stamp=str(int(time.time()*1000))
        sign=base64.b64encode(hmac.new(c['secret_key'].encode(),
            (stamp+'GET'+path).encode(),hashlib.sha256).digest()).decode()
        req=urllib.request.Request(url,method='GET',headers={
            'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':sign,
            'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':stamp,
            'Content-Type':'application/json'})
        try:
            with opener(req,timeout=8) as response:
                if response.status!=200:raise SnapshotFailure('NOT_HTTP_200')
                data=json.load(response)
        except (OSError,ValueError,urllib.error.URLError,TimeoutError) as e:
            raise SnapshotFailure('SIM_READ_'+type(e).__name__) from None
        if not isinstance(data,list) or any(not isinstance(x,dict) for x in data):
            raise SnapshotFailure('INCOMPLETE_'+label.upper())
        if len(data)>=100:raise SnapshotFailure('PAGINATION_MAY_BE_TRUNCATED_'+label.upper())
        result[label]=data
    result['source']='WEEX_SIM_V3_AUTHENTICATED_GET'
    result['complete']=True
    result['productionWrites']=0
    return result

def guardian_readback(path,tid,*,transport=None,credentials_path=CREDENTIALS):
    from weex_partial_guardian_persistent import evaluate
    observed=snapshot(transport=transport,credentials_path=credentials_path)
    return evaluate(path,tid,positions=observed['positions'],algos=observed['algos'],
       regular_orders=observed['regular_orders'],authenticated_sim_readback=observed['complete'])

if __name__=='__main__':
    try:
        r=snapshot()
        print(json.dumps({'status':'SNAPSHOT_OK','source':r['source'],
          'positions':len(r['positions']),'algos':len(r['algos']),
          'regular_orders':len(r['regular_orders']),'productionWrites':0}))
    except SnapshotFailure as err:
        print(json.dumps({'status':'SNAPSHOT_BLOCKED','reason':str(err),'productionWrites':0}))

def guardian_confirm_pending(path,tid,*,transport=None,credentials_path=CREDENTIALS):
    """Recover a previously recorded attempt using ONLY authenticated GET.

    The pending step/fingerprint is read from SQLite. This function cannot
    generate a new request or silently retry the previous one.
    """
    from contextlib import closing
    from weex_partial_guardian_persistent import dbopen,confirm_step
    with closing(dbopen(path)) as db:
        row=db.execute('SELECT pending FROM replacements WHERE trade_id=?',(tid,)).fetchone()
        if row is None:return {'state':'REVIEW_REQUIRED','reason':'UNKNOWN_TRADE','canRetry':False}
        if row['pending'] is None:return {'state':'REVIEW_REQUIRED','reason':'NO_PENDING_STEP','canRetry':False}
        pending=json.loads(row['pending'])
    observed=snapshot(transport=transport,credentials_path=credentials_path)
    return confirm_step(path,tid,step=pending['step'],
       request_fingerprint=pending['fingerprint'],
       positions=observed['positions'],algos=observed['algos'],
       regular_orders=observed['regular_orders'],
       authenticated_sim_readback=observed['complete'])
