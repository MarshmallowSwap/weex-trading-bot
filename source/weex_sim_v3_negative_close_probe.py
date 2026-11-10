"""WEEX simulation-only negative close endpoint probe.

This checks the endpoint with positionId=1 ONLY IF the authenticated
simulation account has zero positions, regular orders, and algo orders.
No real position is opened, and no production endpoint is ever used.
A negative response does not prove that an actual position can be closed.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from pathlib import Path
from weex_sim_v3_guard import SIM_HOST
from weex_sim_v3_auth_readonly import readiness,CREDENTIALS
BASE='https://'+SIM_HOST
READS=('/capi/v3/account/position/allPosition','/capi/v3/openOrders','/capi/v3/openAlgoOrders')
CLOSE='/capi/v3/closePositions'

def call(method,path,credentials,body=''):
    if method=='GET' and path not in READS:raise ValueError('UNAUTHORIZED_READ')
    if method=='POST' and (path!=CLOSE or body!='{"symbol":"BTCUSDT","positionId":1}'):
        raise ValueError('UNAUTHORIZED_WRITE')
    if method not in ('GET','POST'):raise ValueError('UNAUTHORIZED_METHOD')
    ts=str(int(time.time()*1000))
    sign=base64.b64encode(hmac.new(credentials['secret_key'].encode(),
       (ts+method+path+body).encode(),hashlib.sha256).digest()).decode()
    req=urllib.request.Request(BASE+path,
       data=body.encode() if method=='POST' else None,method=method,
       headers={'ACCESS-KEY':credentials['api_key'],'ACCESS-SIGN':sign,
                'ACCESS-PASSPHRASE':credentials['passphrase'],
                'ACCESS-TIMESTAMP':ts,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as err:
        try:result=json.loads(err.read(4096))
        except (ValueError,TypeError):result=None
        return err.code,result

def probe():
    result={'environment':'WEEX_SIM_V3','productionHostContacted':False,
            'realPositionsOpened':0,'canCertifySafeExit':False,
            'status':'BLOCKED'}
    if readiness()['status']!='READY_FOR_READ_ONLY_AUTH_CHECK':
        return {**result,'reason':'SIM_CREDENTIALS_UNAVAILABLE'}
    c=json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    for path in READS:
        status,data=call('GET',path,c)
        if status!=200 or not isinstance(data,list) or len(data)!=0:
            return {**result,'reason':'SIM_NOT_EMPTY_OR_READ_UNAVAILABLE',
                    'failedRead':path,'httpStatus':status}
    # Known invalid numeric positionId; account has zero positions.
    try:
        status,data=call('POST',CLOSE,c,'{"symbol":"BTCUSDT","positionId":1}')
    except Exception as exc:
        return {**result,'reason':'SIM_NEGATIVE_CLOSE_TRANSPORT_FAILED',
                'errorType':type(exc).__name__}
    outcome={'status':'NEGATIVE_CLOSE_PROBE_FINISHED','httpStatus':status,
             'writeRequestsAttempted':1,'realPositionsOpened':0,
             'canCertifySafeExit':False,'productionHostContacted':False}
    if isinstance(data,list):
        outcome['responseKind']='list'
        outcome['closeReportedSuccess']=any(isinstance(x,dict) and x.get('success') is True for x in data)
    elif isinstance(data,dict):
        outcome['responseKind']='dict'
        v=data.get('code')
        if isinstance(v,(str,int)) and str(v).lstrip('-').isdigit():
            outcome['exchangeCode']=str(v)
    else:outcome['responseKind']='other'
    if outcome.get('closeReportedSuccess'):
        outcome['status']='UNEXPECTED_SUCCESS_INVESTIGATE'
    return outcome
if __name__=='__main__':
    try:print(json.dumps(probe()))
    except Exception as exc:print(json.dumps({'status':'BLOCKED','errorType':type(exc).__name__,
                                               'productionHostContacted':False}))
