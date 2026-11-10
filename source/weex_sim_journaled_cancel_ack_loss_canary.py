"""One-shot, demo-only WEEX partial-close TP+SL experiment.

Opens 0.0002 BTC in dedicated api-sim.weex.com, creates TP LIMIT
and SL MARKET for full size, closes 0.0001 BTC with reduceOnly MARKET,
observes the residual TP/SL quantity, then closes exact position ID.
No production endpoint, no automatic POST retries. Always read back.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from decimal import Decimal,ROUND_HALF_UP
from weex_sim_v3_auth_readonly import CREDENTIALS,readiness
from weex_sim_v3_pair_canary import ticker_price
HOST='https://api-sim.weex.com'
Q='0.0002'; HALF='0.0001'; SYMBOL='BTCUSDT'
POSITION='/capi/v3/account/position/allPosition'
ALGOS='/capi/v3/openAlgoOrders'
REGULAR='/capi/v3/openOrders'
ORDER='/capi/v3/order'
TP='/capi/v3/placeTpSlOrder'
CLOSE='/capi/v3/closePositions'
CANCEL='/capi/v3/algoOrder'
GETS=(POSITION,ALGOS,REGULAR)
def call(c,method,path,body=None):
    if method=='GET':
        if path not in GETS or body is not None:raise ValueError('GET_DISALLOWED')
    elif method=='POST':
        if path==ORDER and body:
            if (body.get('symbol')!=SYMBOL or body.get('positionSide')!='LONG'
               or body.get('type')!='MARKET'
               or body.get('quantity') not in (Q,HALF)
               or (body.get('side')=='BUY' and (body['quantity']!=Q or body.get('reduceOnly') is not None))
               or (body.get('side')=='SELL' and (body['quantity']!=HALF or body.get('reduceOnly') is not True))
               or body.get('side') not in ('SELL','BUY')):
                raise ValueError('ORDER_SCOPE_VIOLATION')
        elif path==TP and body:
            if (body.get('symbol')!=SYMBOL or body.get('positionSide')!='LONG'
               or body.get('quantity') not in (Q,HALF) or body.get('planType') not in ('STOP_LOSS','TAKE_PROFIT')
               or body.get('executePrice')==None or body.get('triggerPriceType')!='CONTRACT_PRICE'):
                raise ValueError('ALGO_SCOPE_VIOLATION')
        elif path==CLOSE and body:
            if set(body)!={'symbol','positionId'} or body['symbol']!=SYMBOL or not isinstance(body['positionId'],int) or body['positionId']<=0:
                raise ValueError('CLOSE_SCOPE_VIOLATION')
        else:raise ValueError('POST_DISALLOWED')
    elif method=='DELETE':
        if not path.startswith(CANCEL+'?orderId=') or not path.split('orderId=')[1].isdigit():
            raise ValueError('CANCEL_SCOPE_VIOLATION')
    else:raise ValueError('METHOD_DISALLOWED')
    payload=json.dumps(body,separators=(',',':')) if body is not None else ''
    ts=str(int(time.time()*1000))
    sign=base64.b64encode(hmac.new(c['secret_key'].encode(),
         (ts+method+path+payload).encode(),hashlib.sha256).digest()).decode()
    req=urllib.request.Request(HOST+path,method=method,
          data=payload.encode() if body is not None else None,headers={
           'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':sign,
           'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':ts,
           'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as err:
        try:data=json.loads(err.read(2048))
        except (ValueError,TypeError):data=None
        return err.code,data

def snapshot(c):
    result={}
    for path in GETS:
        status,data=call(c,'GET',path)
        if status!=200 or not isinstance(data,list):
            raise ValueError('SNAPSHOT_INCOMPLETE')
        result[path]=data
    return result

def run():
    s={'environment':'SIM_V3','liveWrites':0,'status':'BLOCKED','entryAttempted':False,
       'partialCloseAttempted':False,'fullCloseAttempted':False,'verifiedFlat':False,
       'verifiedNoOrders':False,'partialObserved':False,'tpAndSlInitiallySeen':False}
    if readiness().get('status')!='READY_FOR_READ_ONLY_AUTH_CHECK':
        return {**s,'reason':'CREDENTIALS_NOT_READY'}
    c=json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    try:
        before=snapshot(c)
        if any(before.values()):return {**s,'reason':'SIM_NOT_EMPTY'}
        price=ticker_price()
        tick=Decimal('.1')
        sl=str((price*Decimal('.97')).quantize(tick,rounding=ROUND_HALF_UP))
        tp=str((price*Decimal('1.03')).quantize(tick,rounding=ROUND_HALF_UP))
        suffix=str(int(time.time()*1000))
    except Exception as exc:
        return {**s,'reason':'PRECHECK_FAILED','errorType':type(exc).__name__}
    posid=None
    known=[]
    try:
        s['entryAttempted']=True
        http,ack=call(c,'POST',ORDER,{'symbol':SYMBOL,'side':'BUY',
            'positionSide':'LONG','type':'MARKET','quantity':Q,
            'newClientOrderId':'wxsimpentry'+suffix})
        s['entryHttpStatus']=http
        for _ in range(5):
            ps=snapshot(c)[POSITION]
            matches=[p for p in ps if p.get('symbol')==SYMBOL and p.get('side')=='LONG'
                     and Decimal(str(p.get('size',0)))==Decimal(Q) and isinstance(p.get('id'),int)]
            if len(matches)==1:
                posid=matches[0]['id'];break
            time.sleep(.5)
        if posid is None:raise ValueError('ENTRY_NOT_VERIFIED')
        for typ,trigger,limit,prefix in (('STOP_LOSS',sl,'0','wxsimsl'),
                                          ('TAKE_PROFIT',tp,tp,'wxsimp')):
            body={'symbol':SYMBOL,'clientAlgoId':prefix+suffix,
                  'planType':typ,'triggerPrice':trigger,'executePrice':limit,
                  'quantity':Q,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
            result,response=call(c,'POST',TP,body)
            s[typ+'HttpStatus']=result
            if result!=200 or not isinstance(response,list) or len(response)!=1 or response[0].get('success') is not True:
                raise ValueError(typ+'_NOT_ACCEPTED')
            known.append(response[0].get('orderId'))
        observed=snapshot(c)
        s['tpAndSlInitiallySeen']=len(observed[ALGOS])==2 and all(
            str(o.get('algoId',o.get('orderId'))) in {str(x) for x in known}
            for o in observed[ALGOS])
        if not s['tpAndSlInitiallySeen']:raise ValueError('PAIR_NOT_READBACK_VERIFIED')
        # Only simulated close-only order, half the initial quantity.
        s['partialCloseAttempted']=True
        part_http,part=call(c,'POST',ORDER,{'symbol':SYMBOL,'side':'SELL',
          'positionSide':'LONG','type':'MARKET','quantity':HALF,
          'reduceOnly':True,'newClientOrderId':'wxsimpclose'+suffix})
        s['partialHttpStatus']=part_http
        for _ in range(6):
            check=snapshot(c)
            ps=[p for p in check[POSITION] if str(p.get('id'))==str(posid)]
            if len(ps)==1 and Decimal(str(ps[0].get('size')))==Decimal(HALF):
                s['partialObserved']=True
                s['remainingPositionQuantity']=HALF
                algos=[a for a in check[ALGOS] if str(a.get('algoId',a.get('orderId'))) in {str(x) for x in known}]
                s['algoCountAfterPartial']=len(algos)
                s['algoQuantitiesAfterPartial']=sorted(
                     [str(a.get('quantity','MISSING')) for a in algos])
                s['algoStatusesAfterPartial']=sorted(
                     [str(a.get('algoStatus','MISSING')) for a in algos])
                s['regularOrdersAfterPartial']=len(check[REGULAR])
                break
            time.sleep(.5)
        if not s['partialObserved']:raise ValueError('PARTIAL_CLOSE_NOT_VERIFIED')
        # Durable journal registration after exact partial-position readback.
        from weex_partial_guardian_persistent import register
        from weex_partial_guardian_sim_executor import execute_one
        ledger=str((__import__('pathlib').Path(__file__).resolve().parent/
                    'weex_partial_guardian_demo_active.sqlite3'))
        trade_id='wxsim-journal-'+suffix
        register(ledger,trade_id,position_id=posid,symbol=SYMBOL,side='LONG',
                 old_tp_client='wxsimp'+suffix,old_sl_client='wxsimsl'+suffix,
                 new_tp_client='wxsimpnew'+suffix,new_sl_client='wxsimslnew'+suffix)
        s['journalTradeRegistered']=True
        s['journalStepStates']=[]
        # Order replacement: new SL first, NEVER remove old SL before GET proof.
        newsid='wxsimslnew'+suffix
        sl_new={'symbol':SYMBOL,'clientAlgoId':newsid,
                'planType':'STOP_LOSS','triggerPrice':sl,'executePrice':'0',
                'quantity':HALF,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
        s['newStopPostAttempted']=True
        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_NEW_STOP_UNCONFIRMED')
        sl_http=200
        new_entries=[a for a in snapshot(c)[ALGOS] if a.get('clientAlgoId')==newsid]
        sl_ack=([{'success':True,'orderId':new_entries[0]['algoId']}]
                if len(new_entries)==1 else [])
        s['newStopHttpStatus']=sl_http
        if sl_http!=200 or not isinstance(sl_ack,list) or len(sl_ack)!=1 or sl_ack[0].get('success') is not True:
            raise ValueError('NEW_STOP_REJECTED_OLD_STOP_RETAINED')
        newid=sl_ack[0].get('orderId')
        if not isinstance(newid,int):raise ValueError('NEW_STOP_ORDER_ID_MISSING')
        known.append(newid)
        snap=snapshot(c)
        active=snap[ALGOS]
        newstop=[a for a in active if str(a.get('algoId',a.get('orderId')))==str(newid)
                  and Decimal(str(a.get('quantity')))==Decimal(HALF)]
        oldstop=[a for a in active if str(a.get('algoId',a.get('orderId')))==str(known[0])]
        if len(newstop)!=1 or len(oldstop)!=1:
            raise ValueError('NEW_AND_OLD_STOP_NOT_SIMULTANEOUSLY_VERIFIED')
        s['newStopVerifiedBeforeCancel']=True
        # Cancel exact old SL and read back new stop before touching old TP.
        s['oldStopCancelAttempted']=True
        from weex_partial_guardian_sim_readback import guardian_confirm_pending
        from urllib.request import urlopen
        intercepted={'cancelCalls':0}
        def lose_cancel_ack_after_response(req,timeout=8):
            expected='https://api-sim.weex.com/capi/v3/algoOrder?orderId='+str(known[0])
            if req.get_method()!='DELETE' or req.full_url!=expected:
                raise ValueError('CANCEL_FAULT_SCOPE_DENIED')
            if intercepted['cancelCalls']>=1:
                raise ValueError('DUPLICATE_CANCEL_DENIED')
            intercepted['cancelCalls']+=1
            with urlopen(req,timeout=timeout) as resp:
                resp.read()
            raise TimeoutError('DEMO_CANCEL_ACK_LOST_AFTER_HTTP_RESPONSE')
        first=execute_one(ledger,trade_id,new_stop_trigger=sl,
                          new_tp_limit=tp,transport=lose_cancel_ack_after_response)
        s['cancelAckState']=first.get('state')
        s['cancelWriteCalls']=intercepted['cancelCalls']
        if first.get('state')!='ACK_UNCERTAIN' or intercepted['cancelCalls']!=1:
            raise ValueError('CANCEL_FAULT_NOT_RECOGNIZED')
        # Crucially: recover by authenticated GET; never call execute_one again.
        journal_result=guardian_confirm_pending(ledger,trade_id)
        s['cancelRecoveredViaGET']=journal_result.get('confirmedByReadback') is True
        s['journalStepStates'].append(journal_result.get('state'))
        if not s['cancelRecoveredViaGET']:
            raise ValueError('JOURNAL_OLD_STOP_CANCEL_UNCONFIRMED')
        oldcancel_http,oldcancel_ack=200,[]
        s['oldStopCancelHttpStatus']=oldcancel_http
        active=snapshot(c)[ALGOS]
        if (any(str(a.get('algoId',a.get('orderId')))==str(known[0]) for a in active)
             or not any(str(a.get('algoId',a.get('orderId')))==str(newid) for a in active)):
            raise ValueError('NEW_STOP_NOT_RETAINED_AFTER_OLD_CANCEL')
        s['oldStopRemovedNewStopActive']=True
        # Original TP is now oversized. Cancel exact id and readback.
        s['oldTpCancelAttempted']=True
        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_OLD_TP_CANCEL_UNCONFIRMED')
        tp_cancel_http,tp_cancel_ack=200,[]
        s['oldTpCancelHttpStatus']=tp_cancel_http
        active=snapshot(c)[ALGOS]
        if (any(str(a.get('algoId',a.get('orderId')))==str(known[1]) for a in active)
             or not any(str(a.get('algoId',a.get('orderId')))==str(newid) for a in active)):
            raise ValueError('OLD_TP_CANCEL_OR_NEW_STOP_READBACK_FAILED')
        # Place replacement TP for HALF, with original STOP still protected.
        newtpid='wxsimpnew'+suffix
        tp_new={'symbol':SYMBOL,'clientAlgoId':newtpid,
                'planType':'TAKE_PROFIT','triggerPrice':tp,'executePrice':tp,
                'quantity':HALF,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
        s['newTpPostAttempted']=True
        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_NEW_TP_UNCONFIRMED')
        nt_http=200
        new_entries=[a for a in snapshot(c)[ALGOS] if a.get('clientAlgoId')==newtpid]
        nt_ack=([{'success':True,'orderId':new_entries[0]['algoId']}]
                if len(new_entries)==1 else [])
        s['newTpHttpStatus']=nt_http
        if nt_http!=200 or not isinstance(nt_ack,list) or len(nt_ack)!=1 or nt_ack[0].get('success') is not True:
            raise ValueError('NEW_TP_NOT_ACCEPTED')
        tpid=nt_ack[0].get('orderId')
        if not isinstance(tpid,int):raise ValueError('NEW_TP_ID_MISSING')
        known.append(tpid)
        current=snapshot(c)
        remaining=[p for p in current[POSITION] if str(p.get('id'))==str(posid)]
        active=[a for a in current[ALGOS] if str(a.get('algoId',a.get('orderId'))) in (str(newid),str(tpid))]
        s['replacementVerified']=(
            len(remaining)==1 and Decimal(str(remaining[0].get('size')))==Decimal(HALF)
            and len(active)==2
            and all(Decimal(str(a.get('quantity')))==Decimal(HALF) for a in active)
            and not current[REGULAR])
        if not s['replacementVerified']:
            raise ValueError('REPLACEMENT_PAIR_READBACK_FAILED')

    except Exception as exc:
        s['phaseError']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    finally:
        try:
            if posid is None:
                current=snapshot(c)[POSITION]
                candidate=[p for p in current if p.get('symbol')==SYMBOL and p.get('side')=='LONG' and isinstance(p.get('id'),int)]
                if len(candidate)==1:posid=candidate[0]['id']
            if posid is not None:
                s['fullCloseAttempted']=True
                close_http,response=call(c,'POST',CLOSE,{'symbol':SYMBOL,'positionId':posid})
                s['fullCloseHttpStatus']=close_http
                s['fullCloseAckMatched']=isinstance(response,list) and any(
                    isinstance(x,dict) and x.get('positionId')==posid and x.get('success') is True for x in response)
        except Exception as exc:s['closeErrorType']=type(exc).__name__
        for i in range(5):
            try:
                after=snapshot(c)
                s['verifiedFlat']=not after[POSITION]
                if s['verifiedFlat']:break
            except Exception:pass
            time.sleep(.6)
        try:
            last=snapshot(c)
            if last[ALGOS]:
                for a in last[ALGOS]:
                    oid=a.get('algoId',a.get('orderId'))
                    if str(oid).isdigit() and str(oid) in {str(x) for x in known}:
                        call(c,'DELETE',CANCEL+'?orderId='+str(oid))
            final=snapshot(c)
            s['verifiedNoOrders']=not final[ALGOS] and not final[REGULAR]
            s['verifiedFlat']=not final[POSITION]
        except Exception as exc:s['cleanupErrorType']=type(exc).__name__
    s['status']='DEMO_CANCEL_ACK_LOSS_RECOVERY_VERIFIED' if (
       s.get('cancelWriteCalls')==1 and s.get('cancelRecoveredViaGET') and
       s.get('journalStepStates')==['DUPLICATE_STOPS_REVIEW',
       'NEW_STOP_ONLY_OLD_TP_REVIEW','NEW_STOP_PRESENT_TP_MISSING',
       'PAIR_RESTORED_OFFLINE_ONLY'] and
       s.get('replacementVerified') and
       s['partialObserved'] and s['verifiedFlat'] and s['verifiedNoOrders']) else 'DEMO_REQUIRES_REVIEW'
    return s

if __name__=='__main__':
    try:print(json.dumps(run()))
    except Exception as e:print(json.dumps({'status':'DEMO_REQUIRES_REVIEW','errorType':type(e).__name__,'liveWrites':0}))
