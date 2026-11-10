"""WEEX V3 simulation-only transport for journaled partial-exit steps.

No production hostname. No position opening. Each order uses an immutable
clientAlgoId. Network errors are uncertain: the caller MUST NOT retry.
Transport cannot claim success without authenticated readback.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from urllib.parse import urlparse
from weex_sim_v3_auth_readonly import CREDENTIALS,readiness
from weex_partial_guardian_persistent import STEPS,canonical
HOST='https://api-sim.weex.com'
PLACE='/capi/v3/placeTpSlOrder'
CANCEL='/capi/v3/algoOrder'
class UncertainWrite(Exception):pass
class UnsafeWrite(Exception):pass

def prepare(step,*,symbol,position_side,quantity,client_algo_id,
            trigger_price=None,execute_price=None,exact_algo_id=None):
    if step not in STEPS or not isinstance(symbol,str) or not symbol or position_side not in ('LONG','SHORT'):
        raise UnsafeWrite('INVALID_SCOPE')
    from decimal import Decimal
    if Decimal(str(quantity))<=0:raise UnsafeWrite('INVALID_QUANTITY')
    if step in (STEPS[0],STEPS[3]):
        typ='STOP_LOSS' if step==STEPS[0] else 'TAKE_PROFIT'
        if not isinstance(client_algo_id,str) or not client_algo_id.startswith('wxsim') or len(client_algo_id)>36:
            raise UnsafeWrite('INVALID_CLIENT_ALGO_ID')
        if Decimal(str(trigger_price))<=0:raise UnsafeWrite('INVALID_TRIGGER')
        if step==STEPS[0]:
            if str(execute_price)!='0':raise UnsafeWrite('STOP_MUST_BE_MARKET')
        elif Decimal(str(execute_price))<=0:raise UnsafeWrite('TP_MUST_BE_LIMIT')
        return 'POST',PLACE,{'symbol':symbol,'positionSide':position_side,
           'quantity':str(quantity),'clientAlgoId':client_algo_id,
           'planType':typ,'triggerPrice':str(trigger_price),
           'executePrice':str(execute_price),'triggerPriceType':'CONTRACT_PRICE'}
    if not isinstance(exact_algo_id,int) or exact_algo_id<=0:
        raise UnsafeWrite('EXACT_ALGO_ID_REQUIRED')
    return 'DELETE',CANCEL+'?orderId='+str(exact_algo_id),None

def send_sim_only(step,request_spec,*,transport=None,credentials_path=CREDENTIALS):
    method,path,body=request_spec
    if readiness(credentials_path)['status']!='READY_FOR_READ_ONLY_AUTH_CHECK':
        raise UnsafeWrite('SIM_CREDS_UNAVAILABLE')
    if step not in STEPS or method != ('POST' if step in (STEPS[0],STEPS[3]) else 'DELETE'):
        raise UnsafeWrite('STEP_METHOD_MISMATCH')
    if not ((method=='POST' and path==PLACE and isinstance(body,dict))
        or (method=='DELETE' and path.startswith(CANCEL+'?orderId=') and body is None)):
        raise UnsafeWrite('PATH_NOT_SCOPED')
    if method=='POST':
        if (body.get('symbol')!='BTCUSDT' or body.get('positionSide')!='LONG'
           or body.get('quantity')!='0.0001'
           or body.get('planType')!=('STOP_LOSS' if step==STEPS[0] else 'TAKE_PROFIT')
           or not body.get('clientAlgoId','').startswith('wxsim')):
            raise UnsafeWrite('CANARY_SCOPE_REQUIRED')
    if method=='DELETE':
        raw=path[len(CANCEL+'?orderId='):]
        if not raw.isdigit() or int(raw)<=0:raise UnsafeWrite('INVALID_EXACT_ORDER_ID')
    c=json.loads(credentials_path.read_text(encoding='utf-8'))
    payload=json.dumps(body,separators=(',',':')) if body is not None else ''
    stamp=str(int(time.time()*1000))
    sign=base64.b64encode(hmac.new(c['secret_key'].encode(),
      (stamp+method+path+payload).encode(),hashlib.sha256).digest()).decode()
    req=urllib.request.Request(HOST+path,method=method,
      data=payload.encode() if body is not None else None,headers={
      'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':sign,
      'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':stamp,
      'Content-Type':'application/json'})
    opener=transport or urllib.request.urlopen
    try:
        with opener(req,timeout=8) as response:
            result=json.load(response)
            status=response.status
    except Exception as exc:
        raise UncertainWrite('WRITE_ACK_UNCERTAIN_'+type(exc).__name__) from None
    # HTTP status is a weak acknowledgement, not a successful order proof.
    return {'status':'ACK_RECEIVED_READBACK_REQUIRED','httpStatus':status,
            'responseKind':type(result).__name__,'authenticatedReadbackRequired':True,
            'canRetry':False,'liveWrites':0}
