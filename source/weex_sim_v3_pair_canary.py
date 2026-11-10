"""WEEX V3 dedicated SIM-ONLY TP LIMIT + SL coexistence canary.

One BTCUSDT minimum-size simulated long. Place SL market first, TP limit
second; verify readbacks; close exact positionId; cleanup exact algo orderIds.
Never sends production requests, never repeats ambiguous entry or close POST.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from decimal import Decimal,ROUND_HALF_UP
from weex_sim_v3_one_shot_canary import request as core_request,empty_account,QTY,SYMBOL,GETS
from weex_sim_v3_auth_readonly import CREDENTIALS,readiness
HOST='https://api-sim.weex.com'
TP='/capi/v3/placeTpSlOrder'
CANCEL='/capi/v3/algoOrder'
TICKER='/capi/v3/market/ticker/24hr?symbol=BTCUSDT'
def guarded_request(method,path,c,body=None):
    allowed=(method=='POST' and path==TP and isinstance(body,dict)) or (
        method=='DELETE' and path.startswith(CANCEL+'?orderId=') and body is None)
    if not allowed:raise ValueError('DENIED_SIM_ORDER_ROUTE')
    if method=='POST':
        if (body.get('symbol')!=SYMBOL or body.get('positionSide')!='LONG'
          or body.get('quantity')!=QTY or body.get('planType') not in ('TAKE_PROFIT','STOP_LOSS')
          or body.get('triggerPriceType')!='CONTRACT_PRICE'
          or not isinstance(body.get('clientAlgoId'),str) or not body['clientAlgoId'].startswith('wxsim')):
            raise ValueError('INVALID_SIM_PROTECTION_SCOPE')
        if (body['planType']=='STOP_LOSS' and body.get('executePrice')!='0') or (
             body['planType']=='TAKE_PROFIT' and Decimal(body.get('executePrice','0'))<=0):
            raise ValueError('UNSAFE_SIM_PROTECTION_EXECUTION')
        payload=json.dumps(body,separators=(',',':'))
    else:
        identifier=path.split('orderId=',1)[1]
        if not identifier.isdigit() or int(identifier)<=0:raise ValueError('INVALID_EXACT_ALGO_ID')
        payload=''
    ts=str(int(time.time()*1000))
    sign_path=path
    signature=base64.b64encode(hmac.new(c['secret_key'].encode(),
       (ts+method+sign_path+payload).encode(),hashlib.sha256).digest()).decode()
    req=urllib.request.Request(HOST+path,method=method,
        data=payload.encode() if method=='POST' else None,
        headers={'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':signature,
          'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':ts,
          'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as resp:return resp.status,json.load(resp)
    except urllib.error.HTTPError as e:
        try:data=json.loads(e.read(4096))
        except (TypeError,ValueError):data=None
        return e.code,data

def ticker_price():
    with urllib.request.urlopen(HOST+TICKER,timeout=8) as response:
        x=json.load(response)
    if isinstance(x,list):x=x[0]
    price=Decimal(str(x['lastPrice']))
    if price<=0:raise ValueError('INVALID_SIM_PRICE')
    return price

def observe_position(c):
    status,p=core_request('GET',GETS[0],c)
    if status!=200 or not isinstance(p,list):raise ValueError('UNREADABLE_POSITIONS')
    return p

def observe_algos(c):
    status,x=core_request('GET',GETS[2],c)
    if status!=200 or not isinstance(x,list):raise ValueError('UNREADABLE_ALGOS')
    return x

def run():
    state={'environment':'WEEX_SIM_V3','productionWrites':0,
           'status':'BLOCKED','entryAttempted':False,'closeAttempted':False,
           'positionClosedVerified':False,'algosClearedVerified':False,
           'tpAccepted':False,'slAccepted':False}
    if readiness().get('status')!='READY_FOR_READ_ONLY_AUTH_CHECK':
        return {**state,'reason':'NO_AUTH'}
    c=json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    try:
        if any(empty_account(c)):return {**state,'reason':'SIM_ACCOUNT_NOT_EMPTY'}
        price=ticker_price()
    except Exception as e:return {**state,'reason':'PREFLIGHT_FAILED','errorType':type(e).__name__}
    # Trigger far from current price; no attempt to earn target net 15 in this canary.
    tick=Decimal('0.1')
    slprice=str((price*Decimal('.99')).quantize(tick,rounding=ROUND_HALF_UP))
    tpprice=str((price*Decimal('1.01')).quantize(tick,rounding=ROUND_HALF_UP))
    suffix=str(int(time.time()*1000))
    position_id=None
    known_algos=[]
    try:
        state['entryAttempted']=True
        e_status,e_ack=core_request('POST','/capi/v3/order',c,{
            'symbol':SYMBOL,'side':'BUY','positionSide':'LONG','type':'MARKET',
            'quantity':QTY,'newClientOrderId':'wxsimpair'+suffix})
        state['entryHttpStatus']=e_status
        for i in range(4):
            positions=observe_position(c)
            match=[p for p in positions if p.get('symbol')==SYMBOL and p.get('side')=='LONG']
            if len(match)==1 and isinstance(match[0].get('id'),int) and Decimal(str(match[0].get('size')))==Decimal(QTY):
                position_id=match[0]['id'];break
            time.sleep(.7)
        if position_id is None:raise ValueError('ENTRY_NOT_EXACTLY_OBSERVED')
        sl={'symbol':SYMBOL,'clientAlgoId':'wxsims'+suffix,
            'planType':'STOP_LOSS','triggerPrice':slprice,'executePrice':'0',
            'quantity':QTY,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
        s_status,s_ack=guarded_request('POST',TP,c,sl)
        state['slHttpStatus']=s_status
        if s_status!=200 or not isinstance(s_ack,list) or len(s_ack)!=1 or s_ack[0].get('success') is not True:
            raise ValueError('STOP_NOT_ACCEPTED')
        state['slAccepted']=True
        if isinstance(s_ack[0].get('orderId'),int):known_algos.append(s_ack[0]['orderId'])
        tp={'symbol':SYMBOL,'clientAlgoId':'wxsimp'+suffix,
            'planType':'TAKE_PROFIT','triggerPrice':tpprice,'executePrice':tpprice,
            'quantity':QTY,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
        t_status,t_ack=guarded_request('POST',TP,c,tp)
        state['tpHttpStatus']=t_status
        if t_status!=200 or not isinstance(t_ack,list) or len(t_ack)!=1 or t_ack[0].get('success') is not True:
            raise ValueError('TP_LIMIT_NOT_ACCEPTED')
        state['tpAccepted']=True
        if isinstance(t_ack[0].get('orderId'),int):known_algos.append(t_ack[0]['orderId'])
        algos=observe_algos(c)
        ids={str(a.get('algoId',a.get('orderId'))) for a in algos}
        state['slAndTpObservedSimultaneously']=all(str(oid) in ids for oid in known_algos) and len(known_algos)==2
        state['observedAlgoCount']=len(algos)
    except Exception as exc:
        state['phaseError']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    finally:
        # If entry filled, always attempt exact-ID close. No broad account close.
        try:
            if position_id is None:
                ps=observe_position(c)
                matches=[p for p in ps if p.get('symbol')==SYMBOL and p.get('side')=='LONG'
                      and isinstance(p.get('id'),int)]
                if len(matches)==1:position_id=matches[0]['id']
            if position_id is not None:
                state['closeAttempted']=True
                close_http,ack=core_request('POST','/capi/v3/closePositions',c,
                                            {'symbol':SYMBOL,'positionId':position_id})
                state['closeHttpStatus']=close_http
                state['closeAckMatched']=isinstance(ack,list) and any(isinstance(a,dict)
                    and a.get('positionId')==position_id and a.get('success') is True for a in ack)
        except Exception as e:state['closeErrorType']=type(e).__name__
        for _ in range(4):
            try:
                ps=observe_position(c)
                if position_id is not None and not any(str(p.get('id'))==str(position_id) for p in ps):
                    state['positionClosedVerified']=True;break
            except Exception:pass
            time.sleep(.7)
        # Cancel exact known algo IDs only if observed outstanding.
        try:
            algos=observe_algos(c)
            outstanding=[a for a in algos if str(a.get('algoId',a.get('orderId'))) in {str(i) for i in known_algos}]
            state['outstandingAfterClose']=len(outstanding)
            for item in outstanding:
                oid=item.get('algoId',item.get('orderId'))
                if str(oid).isdigit():
                    guarded_request('DELETE',CANCEL+'?orderId='+str(oid),c)
            remaining=observe_algos(c)
            state['algosClearedVerified']=not any(
                str(a.get('algoId',a.get('orderId'))) in {str(i) for i in known_algos} for a in remaining)
        except Exception as e:state['cleanupErrorType']=type(e).__name__
    state['status']='SIM_PAIR_CYCLE_VERIFIED' if (
        state['slAccepted'] and state['tpAccepted'] and state.get('slAndTpObservedSimultaneously')
        and state['positionClosedVerified'] and state['algosClearedVerified']
    ) else 'SIM_PAIR_REQUIRES_REVIEW'
    state['fullOcoAndPartialFillVerified']=False
    return state
if __name__=='__main__':
    try:print(json.dumps(run()))
    except Exception as e:print(json.dumps({'status':'SIM_PAIR_REQUIRES_REVIEW',
      'errorType':type(e).__name__,'productionWrites':0}))
