"""ONE-SHOT WEEX V3 SIMULATION CANARY: entry 0.0001 BTC, then exact-id close.

Hardcoded simulation hostname; no production write transport.
Never retries POST on uncertain acknowledgement. Emits sanitized status only.
If a demo exit fails, the demo position may remain open and requires review.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from pathlib import Path
from weex_sim_v3_auth_readonly import CREDENTIALS,readiness
HOST='https://api-sim.weex.com'
GETS=('/capi/v3/account/position/allPosition','/capi/v3/openOrders','/capi/v3/openAlgoOrders')
ENTRY='/capi/v3/order'
CLOSE='/capi/v3/closePositions'
QTY='0.0001'
SYMBOL='BTCUSDT'
def request(method,path,c,body=None):
    if (method,path) not in {(('GET',p)) for p in GETS}|{('POST',ENTRY),('POST',CLOSE)}:
        raise ValueError('DISALLOWED_REQUEST')
    payload=json.dumps(body,separators=(',',':')) if body is not None else ''
    if method=='POST' and path==ENTRY:
        if set(body)!=set(('symbol','side','positionSide','type','quantity','newClientOrderId')) or any((
                body['symbol']!=SYMBOL,body['side']!='BUY',body['positionSide']!='LONG',
                body['type']!='MARKET',body['quantity']!=QTY)):
            raise ValueError('UNSAFE_ENTRY')
    if method=='POST' and path==CLOSE:
        if set(body)!=set(('symbol','positionId')) or body['symbol']!=SYMBOL or not isinstance(body['positionId'],int) or body['positionId']<=0:
            raise ValueError('UNSAFE_CLOSE')
    ts=str(int(time.time()*1000))
    sign=base64.b64encode(hmac.new(c['secret_key'].encode(),(ts+method+path+payload).encode(),hashlib.sha256).digest()).decode()
    req=urllib.request.Request(HOST+path,
         data=payload.encode() if method=='POST' else None,method=method,
         headers={'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':sign,
             'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':ts,
             'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as resp:return resp.status,json.load(resp)
    except urllib.error.HTTPError as err:
        try:response=json.loads(err.read(4096))
        except (TypeError,ValueError):response=None
        return err.code,response

def empty_account(c):
    results=[]
    for path in GETS:
        status,data=request('GET',path,c)
        if status!=200 or not isinstance(data,list):
            raise ValueError('DEMO_SNAPSHOT_UNVERIFIED')
        results.append(data)
    return results

def run():
    state={'environment':'SIMULATION_V3','productionWriteAttempts':0,
           'entryPostAttempted':False,'closePostAttempted':False,
           'positionClosedVerified':False,'status':'BLOCKED'}
    if readiness().get('status')!='READY_FOR_READ_ONLY_AUTH_CHECK':
        return {**state,'reason':'SIM_CREDENTIALS_UNAVAILABLE'}
    c=json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    try:
        snapshots=empty_account(c)
        if any(snapshots):
            return {**state,'reason':'SIM_ACCOUNT_NOT_EMPTY'}
    except Exception as e:
        return {**state,'reason':'DEMO_PRECHECK_FAILED','errorType':type(e).__name__}
    oid='wxsim'+str(int(time.time()*1000))
    entry={'symbol':SYMBOL,'side':'BUY','positionSide':'LONG','type':'MARKET',
           'quantity':QTY,'newClientOrderId':oid}
    state['entryPostAttempted']=True
    try:
        entry_http,ack=request('POST',ENTRY,c,entry)
        state['entryHttpStatus']=entry_http
        state['entryResponseKind']=type(ack).__name__
    except Exception as e:
        state['entryErrorType']=type(e).__name__
    # Reconcile independently, even after network errors. Never resend entry.
    position=None
    for attempt in range(4):
        try:
            positions=request('GET',GETS[0],c)
            if positions[0]==200 and isinstance(positions[1],list):
                candidates=[p for p in positions[1] if p.get('symbol')==SYMBOL and p.get('side')=='LONG']
                if len(candidates)==1:
                    position=candidates[0];break
                if len(candidates)>1:
                    return {**state,'status':'MANUAL_REVIEW','reason':'AMBIGUOUS_DEMO_POSITION'}
        except Exception:pass
        time.sleep(.8)
    if position is None:
        return {**state,'status':'ENTRY_NOT_OBSERVED','reason':'NO_POSITION_OBSERVED_NO_RETRY'}
    state['entryPositionObserved']=True
    if not isinstance(position.get('id'),int) or str(position.get('size')) not in (QTY,'0.00010','0.000100'):
        return {**state,'status':'MANUAL_REVIEW','reason':'ENTRY_POSITION_ID_OR_SIZE_UNEXPECTED'}
    close={'symbol':SYMBOL,'positionId':position['id']}
    state['closePostAttempted']=True
    try:
        close_http,close_response=request('POST',CLOSE,c,close)
        state['closeHttpStatus']=close_http
        state['closeResponseKind']=type(close_response).__name__
        if isinstance(close_response,list):
            state['closeAckMatched']=any(isinstance(x,dict) and x.get('positionId')==close['positionId'] and x.get('success') is True for x in close_response)
        else:state['closeAckMatched']=False
    except Exception as e:
        state['closeErrorType']=type(e).__name__
    # Verify independent readback, never retry closing blindly.
    for attempt in range(5):
        try:
            status,positions=request('GET',GETS[0],c)
            if status==200 and isinstance(positions,list):
                if not any(str(p.get('id'))==str(close['positionId']) for p in positions):
                    state['positionClosedVerified']=True
                    break
        except Exception:pass
        time.sleep(1)
    state['status']='SIM_CLOSED_CONFIRMED' if state['positionClosedVerified'] else 'DEMO_POSITION_STILL_OPEN_REVIEW'
    return state
if __name__=='__main__':
    try:print(json.dumps(run()))
    except Exception as e:print(json.dumps({'status':'MANUAL_REVIEW','reason':'UNHANDLED_ERROR',
                                            'errorType':type(e).__name__,'productionWriteAttempts':0}))
