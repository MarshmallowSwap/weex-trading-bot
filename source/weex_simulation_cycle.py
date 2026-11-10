"""Explicitly authorized one-off minimum simulation TP acceptance/cleanup cycle.

Uses the installed Lifecycle entry/fill/TP logic, a simulation-only transport,
and a separate persistent journal. Never starts a continuous strategy.
"""
import copy, hashlib, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal as D,ROUND_CEILING
from pathlib import Path
import weex_simulation_calibration as base
from weex_simulation_domain import SIM, SimulationGateway, SimulationSession, capture_request, validate_contract
from weex_simulation_depth import assess
from weex_lifecycle import Lifecycle, now
from weex_http_guard import sdk_types

ROOT=Path(r'D:\FUNDSHOT\weex_alerts')
PREVIOUS=ROOT/'simulation_domain'/'authorized_tp_cycle_20261023'
FOLDER=ROOT/'simulation_domain'/'authorized_tp_cycle_20261023_retry1'
TARGET='0.001'

def bind(folder=FOLDER):
    folder.mkdir(parents=True,exist_ok=True)
    base.FILE=folder/'journal.json'
    return folder

def read(operation,**query):
    return SimulationGateway(ROOT/'weex_credentials.json').read(operation,**query)

def public(path,**params):
    s=SimulationSession()
    try:
        r=s.request('GET',SIM+path,params=params,timeout=10)
        if r.status_code!=200:raise ValueError('SIMULATION_PUBLIC_READ_FAILED')
        return r.json()
    finally:s.close()

def context():
    started=now()
    tasks={
      'meta':lambda:public('/capi/v3/market/exchangeInfo',symbol='BTCUSDT'),
      'tiers':lambda:public('/capi/v3/market/riskLimits',symbol='BTCUSDT'),
      'book':lambda:public('/capi/v3/market/depth',symbol='BTCUSDT',limit=15),
      'api':lambda:public('/capi/v3/market/apiTradingSymbols'),
      'settings':lambda:read('get_capi_v3_account_symbolConfig',symbol='BTCUSDT'),
      'fees':lambda:read('get_capi_v3_account_commissionRate',symbol='BTCUSDT'),
      'account':lambda:read('get_capi_v3_account_accountConfig'),
      'balance':lambda:read('get_capi_v3_account_balance'),
      'positions':lambda:read('get_capi_v3_account_position_allPosition'),
      'orders':lambda:base.pages(read,'get_capi_v3_openOrders',identity='orderId',start=0),
      'algos':lambda:base.pages(read,'get_capi_v3_openAlgoOrders',identity='algoId',start=1),
    }
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures={k:pool.submit(fn) for k,fn in tasks.items()}
        data={k:f.result() for k,f in futures.items()}
    meta=next(m for m in data['meta']['symbols'] if m['symbol']=='BTCUSDT')
    evidence=json.loads((ROOT/'simulation_domain'/'settlement_calibration.json').read_text())
    rules=validate_contract(meta,source_host=SIM,evidence=evidence)
    if rules.get('validationMethod')!='EMPIRICAL_MINIMUM_BTC_SIMULATION_ONLY':
        raise ValueError('EXPECTED_MINIMUM_CALIBRATION_SCOPE')
    units=json.loads((ROOT/'simulation_domain'/'depth_unit_evidence.json').read_text())
    book=assess('BTCUSDT',meta,data['book'],units,source_host=SIM)
    price=D(book['bestAsk']);notional=price*D('0.0001')
    tiers=next(r['brackets'] for r in data['tiers'] if r['symbol']=='BTCUSDT')
    applicable=[D(str(t['initialLeverage'])) for t in tiers
                if D(str(t['notionalFloor']))<=notional<D(str(t['notionalCap']))]
    maximum=min(D(str(meta['maxLeverage'])),min(applicable)) if applicable else D(0)
    if maximum!=200 or notional>20:raise ValueError('MINIMUM_CYCLE_LIMIT_CHANGED')
    settings=next(s for s in data['settings'] if s['symbol']=='BTCUSDT')
    fees=data['fees']
    if isinstance(fees,list):fees=next(f for f in fees if f['symbol']=='BTCUSDT')
    if fees['symbol']!='BTCUSDT':raise ValueError('COMMISSION_SYMBOL_MISMATCH')
    fee=D(str(fees['takerCommissionRate']))
    if not 0<=fee<=D('.01'):raise ValueError('COMMISSION_RATE_UNEXPECTED')
    balance=next(b for b in data['balance'] if b['asset']=='USDT')
    p,o,a=data['positions'],data['orders'],data['algos']
    if not isinstance(p,list):raise ValueError('INVALID_POSITIONS')
    ctx={'observedAtMs':started,'complete':True,'apiEnabled':'BTCUSDT' in data['api'],
      'accountCanTrade':data['account'].get('canTrade'),'hedgeMode':data['account'].get('dualSidePosition'),
      'depthUnitVerified':book['depthUnitVerified'],'liquidityPassed':book['spreadBps']<10,
      'marketSignal':'LONG','riskTierVerified':maximum==200,'availableBalance':balance['availableBalance'],
      'positions':p,'openOrders':o,'conditionalOrders':a,'symbolConfig':settings,
      'referencePrice':str(price),'exitFeeRate':str(fee),'maximumPermittedLeverage':str(maximum)}
    if now()-started>5000:raise ValueError('PREFLIGHT_COLLECTION_TOO_SLOW')
    return ctx,rules,meta

class CycleSession(base.OnceSession):
    def request(self,method,url,**kwargs):
        if self.kind not in ('TP','CANCEL_TP'):
            return super().request(method,url,**kwargs)
        if self.kind in self.state['records']:raise PermissionError('CYCLE_WRITE_ALREADY_DISPATCHED')
        if kwargs.get('json') is not None:raise PermissionError('ALTERNATIVE_BODY_BLOCKED')
        if self.kind=='TP':
            if method!='POST' or url!=SIM+'/capi/v3/placeTpSlOrder':raise PermissionError('SIMULATION_TP_ONLY')
            p=self.payload
            if json.loads(kwargs.get('data',b'{}'))!=p or p!=self.state.get('tpRequest'):
                raise PermissionError('TP_PAYLOAD_MISMATCH')
            allowed={'symbol','clientAlgoId','planType','triggerPrice','executePrice','quantity',
                     'positionSide','triggerPriceType','reduceOnly','closePosition'}
            trigger_floor=D(self.state['entryObservation']['avgPrice'])
            if self.state.get('cycleScope')=='MINIMUM_SIMULATION_TECHNICAL_MARK_TRIGGER_300_SECONDS':
                mark=self.state.get('technicalMarkSnapshot',{})
                if mark.get('sourceHost')!=SIM or mark.get('symbol')!='BTCUSDT':
                    raise PermissionError('TECHNICAL_MARK_SOURCE_REQUIRED')
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(mark['observedAt'])).total_seconds()
                trigger_floor=D(mark['price'])
                policy=self.state.get('technicalTriggerPolicy')
                if policy=='MARK_PLUS_ONE_TICK':reference=trigger_floor
                elif policy=='MARK_WITH_LATENCY_BUFFER':
                    reference=max(trigger_floor,D(self.state['entryObservation']['avgPrice']))*D('1.0002')
                else:raise PermissionError('TECHNICAL_POLICY_REQUIRED')
                expected=(reference/D('.1')).to_integral_value(rounding=ROUND_CEILING)*D('.1')+D('.1')
                if (not 0<=age<=30 or not trigger_floor.is_finite() or trigger_floor<=0
                        or D(p['triggerPrice'])!=expected):
                    raise PermissionError('TECHNICAL_TRIGGER_MISMATCH')
            if (set(p)!=allowed or p['symbol']!='BTCUSDT' or p['positionSide']!='LONG'
                  or p['planType']!='TAKE_PROFIT' or p['reduceOnly'] is not True
                  or p['closePosition'] is not False or p['executePrice']!='0'
                  or p['triggerPriceType']!='MARK_PRICE' or not 0<D(p['quantity'])<=D('0.0001')
                  or D(p['quantity'])!=D(self.state['positionDuring']['size'])
                  or D(p['triggerPrice'])<=trigger_floor):
                raise PermissionError('UNSCOPED_TP')
        else:
            owned=self.state.get('tpObservation',{})
            if (str(owned.get('algoId'))!=str(self.payload['query']['orderId'])
                    or owned.get('clientAlgoId')!=self.state['tpRequest']['clientAlgoId']
                    or owned.get('symbol')!='BTCUSDT'):
                raise PermissionError('TP_CANCEL_OWNERSHIP_REQUIRED')
            if (method!='DELETE' or url!=SIM+'/capi/v3/algoOrder?orderId='+str(owned['algoId'])
                    or kwargs.get('data') not in (None,'',b'')):
                raise PermissionError('ONLY_OWNED_TP_CANCEL')
        self.state['records'][self.kind]={'state':'DISPATCHED_RESPONSE_UNKNOWN','payload':self.payload,
                                        'at':datetime.now(timezone.utc).isoformat()}
        base.save(self.state)
        kwargs['allow_redirects']=False
        response=self.network.request(method=method,url=url,**kwargs)
        if 300<=response.status_code<400:raise PermissionError('CYCLE_REDIRECT_BLOCKED')
        return response

def send(state,kind,operation,payload):
    if kind in state['records']:
        record=state['records'][kind]
        if record.get('payload')!=payload:raise PermissionError('IMMUTABLE_CYCLE_REQUEST')
        if record.get('state')=='RESPONSE_RECEIVED':return record['response']
        raise RuntimeError('UNCERTAIN_WRITE_RECONCILE_WITHOUT_RETRY')
    capture_request(operation,payload)
    config,contract,_=sdk_types();creds=json.loads((ROOT/'weex_credentials.json').read_text())
    session=CycleSession(state,kind,payload)
    client=contract(config_rest_api=config(base_path=SIM,api_key=creds['api_key'],api_secret=creds['secret_key'],
        passphrase=creds['passphrase'],session=session,max_retries=0,timeout=10))
    try:
        result=client.rest_api.execute_operation(operation,payload)
        state['records'][kind].update(state='RESPONSE_RECEIVED',httpStatus=result.status_code,response=result.data)
        base.save(state)
        return result.data
    except Exception as exc:
        if kind in state['records']:
            state['records'][kind]['errorType']=type(exc).__name__
            code=getattr(exc,'code',None)
            if isinstance(code,(int,str)):state['records'][kind]['errorCode']=code
            # This exact HTTP 400 parameter rejection is definitive; timeouts,
            # 5xx and all other ambiguous responses still require reconciliation.
            if getattr(exc,'status_code',None)==400 and str(code)=='-1140':
                failure={'success':False,'errorCode':code,'errorMessage':'PARAMETER_VALIDATION_REJECTED'}
                try:
                    body=json.loads(getattr(exc,'raw_body','{}'))
                    message=body.get('msg') or body.get('message')
                    if isinstance(message,str):
                        for secret in creds.values():
                            if isinstance(secret,str) and secret:message=message.replace(secret,'[REDACTED]')
                        failure['errorMessage']=message[:500]
                except (ValueError,TypeError,AttributeError):pass
                response=[failure] if kind=='TP' else failure
                state['records'][kind].update(state='RESPONSE_RECEIVED',httpStatus=400,
                    exchangeRejected=True,response=response)
                base.save(state)
                return response
            base.save(state)
        raise RuntimeError('CYCLE_DISPATCH_'+kind+'_REQUIRES_RECONCILIATION') from None
    finally:session.close()

class Gateway:
    def __init__(self,state):self.state=state;self.engine=None
    def read(self,op,**query):return read(op,**query)
    def write(self,op,payload):
        if op=='post_capi_v3_order' and payload==self.state['entry']:
            return send(self.state,'ENTRY',op,payload)
        if op=='post_capi_v3_placeTpSlOrder':
            item=self.engine.get(self.state['tradeId']);owned=item['owned']
            if not owned or owned['tpRequest']!=payload:raise PermissionError('LIFECYCLE_TP_BINDING')
            order=base.wait_order(self.state,'ENTRY',read)
            positions=read('get_capi_v3_account_position_allPosition')
            if (len(positions)!=1 or str(positions[0].get('id'))!=owned['positionId']
                    or D(positions[0]['size'])!=D(owned['quantity'])):
                raise PermissionError('TP_POSITION_CHANGED')
            self.state.update(entryObservation=order,positionDuring=positions[0],tpRequest=payload)
            base.save(self.state)
            return send(self.state,'TP',op,payload)
        if op=='delete_capi_v3_order':
            row=base.observe_order(self.state,'ENTRY',read)
            if not row or str(row['orderId'])!=str(payload['query']['orderId']):
                raise PermissionError('ONLY_OWNED_ENTRY_REMAINDER')
            return send(self.state,'CANCEL_REMAINDER',op,payload)
        raise PermissionError('UNAUTHORIZED_CYCLE_OPERATION')

class SimulationCycleLifecycle(Lifecycle):
    def observations(self,item):
        """Concurrent read-only snapshot, retaining all base lifecycle validation."""
        started=now();original=self.gateway
        ack=self.writes(item['id']).get('ENTRY',{}).get('response') or {}
        if not isinstance(ack,dict) or not ack.get('orderId'):
            return super().observations(item)
        symbol=item['symbol'];oid=ack['orderId']
        requests=[
          ('get_capi_v3_openOrders',{'page':0,'limit':100,'symbol':symbol}),
          ('get_capi_v3_order',{'orderId':oid}),
          ('get_capi_v3_userTrades',{'symbol':symbol,'orderId':oid,'limit':100}),
          ('get_capi_v3_account_position_allPosition',{}),
          ('get_capi_v3_openAlgoOrders',{'page':1,'limit':100,'symbol':symbol}),
          ('get_capi_v3_allAlgoOrders',{'symbol':symbol,'startTime':item['created']-1000,'endTime':started,'limit':1000}),
        ]
        def key(op,q):
            # History bounds start at the same trade. The cached end is earlier
            # than the base validator's end by only this snapshot's elapsed time.
            return op,json.dumps({k:str(v) for k,v in q.items() if k!='endTime'},sort_keys=True)
        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            pending=[(op,q,pool.submit(original.read,op,**q)) for op,q in requests]
            cached={key(op,q):f.result() for op,q,f in pending}
        class Snapshot:
            def read(self,op,**query):
                k=key(op,query)
                if k in cached:return copy.deepcopy(cached[k])
                return original.read(op,**query)
        self.gateway=Snapshot()
        try:
            result=super().observations(item)
            if now()-started>5000:raise ValueError('SNAPSHOT_TOO_SLOW')
            return result
        finally:self.gateway=original

def engine_for(state,folder):
    cfg=json.loads((ROOT/'weex_ai_risk_config.json').read_text())
    if cfg['execution']['enabled'] is not False or cfg['execution']['mode']!='PRETRADE':
        raise PermissionError('PRODUCTION_MUST_REMAIN_DISABLED')
    # The generic lifecycle's LIVE label permits its state machine to dispatch;
    # only this in-memory one-off configuration uses it, with the fixed SIM gateway.
    cfg=copy.deepcopy(cfg);cfg['execution'].update(enabled=True,mode='LIVE')
    cfg['strategySettings']['targetNetProfitUSDT']=TARGET
    cfg['telegramSettings']['maxConcurrentPositions']['default']=1
    gateway=Gateway(state)
    engine=SimulationCycleLifecycle(folder/'lifecycle.sqlite3',gateway,lambda:copy.deepcopy(cfg))
    gateway.engine=engine
    return engine

def prepare():
    folder=bind()
    previous=json.loads((PREVIOUS/'journal.json').read_text())
    if previous.get('status')!='CLOSED_VERIFIED' or any(previous['finalInventory'].values()):
        raise PermissionError('PREVIOUS_ATTEMPT_MUST_BE_CLOSED')
    if base.FILE.exists():
        state=json.loads(base.FILE.read_text())
        if state.get('records') or state.get('tradeId') or state.get('host')!=SIM:
            raise PermissionError('CYCLE_JOURNAL_ALREADY_EXISTS_USE_RESUME')
        # Resume only a preparation interrupted before lifecycle creation or dispatch.
        state['preparationResumes']=state.get('preparationResumes',0)+1
    else:
        base.prepare()
        state=json.loads(base.FILE.read_text())
    ctx,rules,meta=context()
    state['createdAt']=datetime.now(timezone.utc).isoformat()
    if any(ctx[k] for k in ('positions','openOrders','conditionalOrders')):
        raise PermissionError('SIMULATION_ACCOUNT_NOT_EMPTY')
    price=D(ctx['referencePrice']);qty=D('0.0001');fee=D(ctx['exitFeeRate'])
    plan={'orderPreview':state['entry'],'requestedLeverage':'200','beforePositions':[],
          'targetNetProfitUSDT':TARGET,'exitFeeRate':str(fee),
          'requiredMarginAndEntryFeeUSDT':str(qty*price/200+qty*price*fee),
          'sizing':{'priceTick':str(rules['priceTick']),'notionalUSDT':str(qty*price)}}
    state['authorization']='User: procedi... sei autorizzato per tutto; proposed simulation TP cycle only'
    state['retryOf']=str(PREVIOUS)
    state['retryReason']='Previous attempt closed safely before TP due to sequential snapshot latency; read-only snapshot parallelized'
    state['cycleScope']='MINIMUM_SIMULATION_TP_ACCEPTANCE_AND_CLEANUP'
    state['metadataSnapshot']=meta
    engine=engine_for(state,folder)
    item=engine.prepare('simulation-tp-cycle-'+state['createdAt'],plan)
    state.update(tradeId=item['id'],entry=item['plan']['entry'],testNetTarget=TARGET,
        exitTemplate={**state['exitTemplate'],'newClientOrderId':'wxclose_'+item['id'][8:]})
    base.save(state)
    # Guard/capture both lifecycle entry and future cancellations before network writes.
    engine.guard(item,ctx)
    capture_request('post_capi_v3_order',state['entry'])
    capture_request('delete_capi_v3_algoOrder',{'query':{'orderId':'1'}})
    print(json.dumps({'status':'PREPARED','host':SIM,'quantity':'0.0001','leverage':200,'testNetTarget':TARGET}))

def find_tp(state):
    if not state.get('tpRequest'):return None
    cid=state['tpRequest']['clientAlgoId']
    opened=base.pages(read,'get_capi_v3_openAlgoOrders',identity='algoId',start=1,symbol='BTCUSDT')
    history=read('get_capi_v3_allAlgoOrders',symbol='BTCUSDT',
        startTime=int(datetime.fromisoformat(state['createdAt']).timestamp()*1000)-60000,
        endTime=now()+30000,limit=1000)
    if not isinstance(history,dict) or history.get('hasMore') is not False or not isinstance(history.get('orders'),list):
        raise RuntimeError('INCOMPLETE_TP_HISTORY')
    rows={str(a['algoId']):a for a in history['orders'] if a.get('clientAlgoId')==cid}
    for a in opened:
        if a.get('clientAlgoId')==cid:rows[str(a['algoId'])]=a
    if len(rows)>1:raise RuntimeError('AMBIGUOUS_OWNED_TP')
    if not rows:return None
    row=next(iter(rows.values()))
    if row.get('symbol')!='BTCUSDT':raise RuntimeError('TP_SYMBOL_MISMATCH')
    response=state['records'].get('TP',{}).get('response')
    if isinstance(response,list) and len(response)==1 and response[0].get('orderId'):
        if str(response[0]['orderId'])!=str(row['algoId']):raise RuntimeError('TP_ACK_MISMATCH')
    state['tpObservation']=row;base.save(state)
    return row

def cleanup(state,engine):
    entry=base.wait_order(state,'ENTRY',read)
    qty=D(entry['executedQty'])
    if not 0<=qty<=D('0.0001'):raise RuntimeError('UNEXPECTED_CYCLE_FILL')
    try:tp=find_tp(state)
    except Exception as exc:
        state['tpCleanupReadError']=type(exc).__name__;base.save(state);tp=None
    if tp and tp['algoStatus'] in ('NEW','UNTRIGGERED'):
        try:send(state,'CANCEL_TP','delete_capi_v3_algoOrder',{'query':{'orderId':str(tp['algoId'])}})
        except RuntimeError:pass  # Reconcile the same ID; never repeat uncertain DELETE.
        for _ in range(8):
            try:tp=find_tp(state)
            except Exception:tp=None
            if tp and tp['algoStatus'] not in ('NEW','UNTRIGGERED'):break
            time.sleep(.5)
        # A reduce-only close is still safe if cancellation is temporarily uncertain.
    if 'EXIT' not in state['records']:
        positions=read('get_capi_v3_account_position_allPosition')
        if positions:
            if (len(positions)!=1 or positions[0].get('symbol')!='BTCUSDT'
                    or positions[0].get('side')!='LONG' or not 0<D(positions[0]['size'])<=qty):
                raise RuntimeError('CLEANUP_POSITION_NOT_ATTRIBUTABLE')
            owned=engine.get(state['tradeId']).get('owned')
            if owned and str(positions[0]['id'])!=owned['positionId']:
                raise RuntimeError('CLEANUP_POSITION_ID_CHANGED')
            state['positionDuring']=positions[0];base.save(state)
            try:send(state,'EXIT','post_capi_v3_order',{**state['exitTemplate'],'quantity':positions[0]['size']})
            except RuntimeError:pass  # Read back the same client ID after an uncertain close.
    exits=[]
    if 'EXIT' in state['records']:
        exits.append(base.wait_order(state,'EXIT',read))
    tp=find_tp(state)
    if tp and tp.get('actualOrderId'):
        close=read('get_capi_v3_order',orderId=tp['actualOrderId'])
        exits.append(close)
    if qty>0 and sum(D(o['executedQty']) for o in exits)!=qty:
        raise RuntimeError('CLEANUP_CLOSE_TOTAL_NOT_CONFIRMED')
    if any(o['symbol']!='BTCUSDT' or o['side']!='SELL' or o['positionSide']!='LONG'
           or o.get('reduceOnly') is not True or o['status'] not in ('FILLED','CANCELED','EXPIRED') for o in exits):
        raise RuntimeError('CLEANUP_EXIT_BINDING')
    p,o,a=base.inventory(read)
    state['finalInventory']={'positions':len(p),'ordinaryOrders':len(o),'conditionalOrders':len(a)}
    if p or o or a:raise RuntimeError('CLEANUP_FINAL_INVENTORY_NOT_EMPTY')
    state['entryFills']=read('get_capi_v3_userTrades',symbol='BTCUSDT',orderId=entry['orderId'],limit=100)
    engine.fills(entry,state['entryFills'])
    state['exitOrders']=exits;state['exitFills']=[]
    for order in exits:
        fills=read('get_capi_v3_userTrades',symbol='BTCUSDT',orderId=order['orderId'],limit=100)
        if not isinstance(fills,list) or len(fills)>=100:raise RuntimeError('CLOSE_FILLS_INCOMPLETE')
        engine.fills(order,fills);state['exitFills'].extend(fills)
    state['productionConfigUnchanged']=hashlib.sha256((ROOT/'weex_ai_risk_config.json').read_bytes()).hexdigest()==state['productionConfigSha256']
    state['status']='CLOSED_VERIFIED';state['finishedAt']=datetime.now(timezone.utc).isoformat()
    state['takeProfitTriggered']=bool(tp and tp.get('actualOrderId'))
    state['takeProfitAcceptancePassed']=state.get('protectedObserved',False)
    base.save(state)
    engine.state(state['tradeId'],'CLOSED',{'source':'AUTHORIZED_SIMULATION_TEST_CLEANUP',
        'takeProfitAcceptancePassed':state['takeProfitAcceptancePassed'],'takeProfitTriggered':state['takeProfitTriggered']})
    print(json.dumps({k:state[k] for k in ('status','takeProfitAcceptancePassed','takeProfitTriggered','finalInventory','productionConfigUnchanged')}))

def execute():
    folder=bind();state=json.loads(base.FILE.read_text())
    if state['host']!=SIM or state.get('cycleScope')!='MINIMUM_SIMULATION_TP_ACCEPTANCE_AND_CLEANUP':
        raise PermissionError('CYCLE_SCOPE_REQUIRED')
    if state['status']=='CLOSED_VERIFIED':
        print(json.dumps({'status':state['status'],'repeatEntry':False}));return
    engine=engine_for(state,folder)
    try:
        if 'ENTRY' not in state['records']:
            if hashlib.sha256((ROOT/'weex_ai_risk_config.json').read_bytes()).hexdigest()!=state['productionConfigSha256']:
                raise PermissionError('PRODUCTION_CONFIG_CHANGED')
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(state['createdAt'])).total_seconds()
            if not 0<=age<=300:raise PermissionError('CYCLE_PLAN_EXPIRED')
            ctx,_,_=context()
            result=engine.advance(state['tradeId'],lambda _:ctx)
        else:result=engine.reconcile(state['tradeId'])
        for _ in range(8):
            state['lastLifecycleState']=result['state'];base.save(state)
            print(json.dumps({'lifecycleState':result['state']}),flush=True)
            if result['state']=='PROTECTED':
                state['protectedObserved']=True
                state['protectedTpRequest']=engine.get(state['tradeId'])['owned']['tpRequest']
                state['protectedTpObservation']=find_tp(state)
                base.save(state);break
            if result['state'] in ('CLOSED','REJECTED','REVIEW_REQUIRED','PREFLIGHT_BLOCKED','STOP_BEFORE_SUBMISSION'):
                state['lifecycleResult']=result.get('detail') or result;base.save(state);break
            if not engine.writes(state['tradeId']).get('ENTRY'):break
            time.sleep(.5);result=engine.reconcile(state['tradeId'])
    except Exception as exc:
        state['cycleErrorType']=type(exc).__name__
        if type(exc) in (RuntimeError,PermissionError,ValueError):state['cycleError']=str(exc)
        base.save(state)
    finally:
        if 'ENTRY' in state['records']:
            cleanup(state,engine)
        else:
            print(json.dumps({'status':'STOPPED_WITHOUT_ORDER','reason':state.get('cycleError') or state.get('lastLifecycleState')}))

if __name__=='__main__':
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['execute-authorized']:execute()
        else:raise PermissionError('EXPLICIT_ONE_OFF_CYCLE_COMMAND_REQUIRED')
    except Exception as exc:
        print(json.dumps({'status':'REVIEW_REQUIRED','errorType':type(exc).__name__,
          'reason':str(exc) if type(exc) in (ValueError,RuntimeError,PermissionError) else 'SEE_JOURNAL'}))
        raise SystemExit(1)
