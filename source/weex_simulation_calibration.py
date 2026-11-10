"""User-authorized minimum-size simulation calibration. Never enables the bot.

One entry, optional cancellation of its remainder, one reduce-only exit. Durable
dispatch records prevent retries after uncertain responses. Fixed simulation host.
"""
import json,sys,time,os,hashlib
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
ROOT=Path(r'D:\FUNDSHOT\weex_alerts');BASE=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.append(str(ROOT))
from weex_simulation_domain import SIM,SimulationSession,SimulationGateway,capture_request
from weex_simulation_depth import assess
from weex_http_guard import sdk_types
from weex_execution_readonly import pages
FILE=BASE/'minimal_simulation_calibration.json'

def save(state):
    temp=FILE.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(state,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    temp.replace(FILE)

def inventory(read):
    p=read('get_capi_v3_account_position_allPosition')
    if not isinstance(p,list):raise ValueError('INVALID_POSITIONS')
    o=pages(read,'get_capi_v3_openOrders',identity='orderId',start=0)
    a=pages(read,'get_capi_v3_openAlgoOrders',identity='algoId',start=1)
    return p,o,a

def prepare():
    if FILE.exists():raise PermissionError('CALIBRATION_ALREADY_PREPARED_USE_EXISTING_JOURNAL')
    config_bytes=(ROOT/'weex_ai_risk_config.json').read_bytes();cfg=json.loads(config_bytes)
    assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
    gateway=SimulationGateway(ROOT/'weex_credentials.json');read=gateway.read
    if any(inventory(read)):raise PermissionError('SIMULATION_ACCOUNT_NOT_EMPTY')
    account=read('get_capi_v3_account_accountConfig')
    assert account.get('canTrade') is True and account.get('dualSidePosition') is True
    settings=next(r for r in read('get_capi_v3_account_symbolConfig',symbol='BTCUSDT') if r['symbol']=='BTCUSDT')
    assert settings['marginType']=='CROSSED' and D(settings['crossLeverage'])==200
    session=SimulationSession()
    def public(path,**params):
        r=session.request('GET',SIM+path,params=params,timeout=10)
        if r.status_code!=200:raise ValueError('PUBLIC_READ_FAILED')
        return r.json()
    meta=next(r for r in public('/capi/v3/market/exchangeInfo',symbol='BTCUSDT')['symbols'] if r['symbol']=='BTCUSDT')
    assert meta['quoteAsset']==meta['marginAsset']=='USDT' and meta['contractType']=='PERPETUAL'
    assert D(str(meta['minOrderSize']))==D('0.0001') and meta['quantityPrecision']==4 and D(str(meta['maxLeverage']))==200
    assert 'BTCUSDT' in public('/capi/v3/market/apiTradingSymbols')
    brackets=next(r['brackets'] for r in public('/capi/v3/market/riskLimits',symbol='BTCUSDT') if r['symbol']=='BTCUSDT')
    book=public('/capi/v3/market/depth',symbol='BTCUSDT',limit=15)
    evidence=json.loads((ROOT/'simulation_domain'/'depth_unit_evidence.json').read_text())
    check=assess('BTCUSDT',meta,book,evidence,source_host=SIM)
    assert check['depthUnitVerified'] and check['spreadBps']<10
    price=D(check['bestAsk']);qty=D('0.0001');notional=price*qty
    assert notional<=20 and notional/200<=5
    assert any(D(str(b['notionalFloor']))<=notional<D(str(b['notionalCap'])) and D(str(b['initialLeverage']))>=200 for b in brackets)
    balance=next(r for r in read('get_capi_v3_account_balance') if r['asset']=='USDT')
    assert D(balance['availableBalance'])>=5
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    entry={'symbol':'BTCUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
           'quantity':'0.0001','newClientOrderId':'wxcal_'+stamp+'_in','reduceOnly':False}
    exit_template={**entry,'side':'SELL','newClientOrderId':'wxcal_'+stamp+'_out','reduceOnly':True}
    capture_request('post_capi_v3_order',entry);capture_request('post_capi_v3_order',exit_template)
    state={'createdAt':datetime.now(timezone.utc).isoformat(),'host':SIM,'status':'PREPARED',
      'authorization':'User: parti con il collaudo minimo; simulation entry and immediate close only',
      'productionConfigSha256':hashlib.sha256(config_bytes).hexdigest(),'entry':entry,'exitTemplate':exit_template,
      'observedLeverage':'200','metadataFlag':meta.get('forwardContractFlag'),
      'calibrationHypothesis':'USDT-linear settlement; deliberately measured, not assumed validated for strategy trading',
      'referenceAsk':str(price),'expectedLinearNotional':str(notional),'expectedLinearInitialMargin':str(notional/200),
      'records':{},'positionBefore':0,'ordinaryOrdersBefore':0,'conditionalOrdersBefore':0,'strategyTradingEnabled':False}
    save(state);session.close()
    print(json.dumps({k:state[k] for k in ('status','host','referenceAsk','expectedLinearNotional','expectedLinearInitialMargin')}))

class OnceSession:
    def __init__(self,state,kind,payload,network=None):
        self.state,self.kind,self.payload=state,kind,payload
        if network is None:
            import requests
            network=requests.Session()
        self.network=network
    def request(self,method,url,**kwargs):
        kind=self.kind
        if kind not in ('ENTRY','EXIT','CANCEL_REMAINDER'):raise PermissionError('UNKNOWN_CALIBRATION_ACTION')
        if kind in self.state['records']:raise PermissionError('CALIBRATION_WRITE_ALREADY_DISPATCHED')
        if kind=='CANCEL_REMAINDER':
            expected_url=SIM+'/capi/v3/order?orderId='+str(self.payload['query']['orderId'])
            if method!='DELETE' or url!=expected_url or kwargs.get('data') not in (None,'',b''):raise PermissionError('ONLY_OWNED_REMAINDER_CANCEL')
        else:
            if method!='POST' or url!=SIM+'/capi/v3/order':raise PermissionError('SIMULATION_ORDER_ONLY')
            if json.loads(kwargs.get('data',b'{}'))!=self.payload:raise PermissionError('CALIBRATION_PAYLOAD_MISMATCH')
            expected=self.state['entry'] if kind=='ENTRY' else self.state['exitTemplate']
            if set(self.payload)!=set(expected):raise PermissionError('UNEXPECTED_CALIBRATION_FIELDS')
            for k in expected:
                if k!='quantity' and self.payload.get(k)!=expected[k]:raise PermissionError('UNSCOPED_CALIBRATION_ORDER')
            if kind=='ENTRY' and self.payload['quantity']!='0.0001':raise PermissionError('MINIMUM_ENTRY_ONLY')
            if kind=='EXIT' and (self.payload.get('reduceOnly') is not True or not 0<D(self.payload['quantity'])<=D('0.0001')):
                raise PermissionError('ONLY_MINIMUM_REDUCE_ONLY_EXIT')
            if kind=='EXIT':
                owned=self.state.get('positionDuring',{})
                if (owned.get('symbol')!='BTCUSDT' or owned.get('side')!='LONG'
                        or D(str(owned.get('size','0')))!=D(self.payload['quantity'])
                        or 'entryObservation' not in self.state):raise PermissionError('EXIT_OWNERSHIP_REQUIRED')
        if kwargs.get('json') is not None:raise PermissionError('ALTERNATIVE_BODY_BLOCKED')
        self.state['records'][kind]={'state':'DISPATCHED_RESPONSE_UNKNOWN','payload':self.payload,
          'at':datetime.now(timezone.utc).isoformat()};save(self.state)
        kwargs['allow_redirects']=False
        response=self.network.request(method=method,url=url,**kwargs)
        if 300<=response.status_code<400:raise PermissionError('CALIBRATION_REDIRECT_BLOCKED')
        return response
    def close(self):self.network.close()

def dispatch(state,kind,payload):
    if kind in state['records']:return
    operation='delete_capi_v3_order' if kind=='CANCEL_REMAINDER' else 'post_capi_v3_order'
    capture_request(operation,payload)
    config,contract,_=sdk_types();creds=json.loads((ROOT/'weex_credentials.json').read_text())
    client=contract(config_rest_api=config(base_path=SIM,api_key=creds['api_key'],api_secret=creds['secret_key'],
      passphrase=creds['passphrase'],session=OnceSession(state,kind,payload),max_retries=0,timeout=10))
    try:
        r=client.rest_api.execute_operation(operation,payload)
        state['records'][kind].update(state='RESPONSE_RECEIVED',httpStatus=r.status_code,response=r.data)
    except Exception as exc:
        state['records'].setdefault(kind,{'state':'NOT_DISPATCHED'})['errorType']=type(exc).__name__
        code=getattr(exc,'code',None)
        if isinstance(code,(int,str)):state['records'][kind]['errorCode']=code
        if getattr(exc,'status_code',None) in (400,401,403,404):
            state['records'][kind]['state']='EXCHANGE_REJECTED'
    save(state)

def observe_order(state,kind,read):
    record=state['records'].get(kind,{})
    ack=record.get('response',{})
    cid=state['entry']['newClientOrderId'] if kind=='ENTRY' else state['exitTemplate']['newClientOrderId']
    if isinstance(ack,dict) and ack.get('orderId'):
        row=read('get_capi_v3_order',orderId=ack['orderId'])
        candidates=[row] if isinstance(row,dict) else []
    else:
        candidates=read('get_capi_v3_order_history',symbol='BTCUSDT',page=0,limit=100,
            startTime=int(datetime.fromisoformat(state['createdAt']).timestamp()*1000)-60000,endTime=int(time.time()*1000))
    found=[r for r in candidates if r.get('clientOrderId')==cid]
    if len(found)!=1:return None
    row=found[0]
    expected_side='BUY' if kind=='ENTRY' else 'SELL'
    if row.get('symbol')!='BTCUSDT' or row.get('positionSide')!='LONG' or row.get('side')!=expected_side:
        raise PermissionError('ORDER_OWNERSHIP_MISMATCH')
    state[kind.lower()+'Observation']=row;save(state)
    return row

def wait_order(state,kind,read):
    for _ in range(10):
        try:
            row=observe_order(state,kind,read)
            if row and row.get('status') in ('FILLED','CANCELED','EXPIRED','REJECTED'):return row
            if row and kind=='ENTRY' and row.get('status')=='PARTIALLY_FILLED':
                dispatch(state,'CANCEL_REMAINDER',{'query':{'orderId':row['orderId']}})
        except Exception as exc:
            state['lastReadErrorType']=type(exc).__name__;save(state)
        time.sleep(.5)
    raise RuntimeError(kind+'_NOT_TERMINAL_NO_RETRY')

def execute():
    state=json.loads(FILE.read_text())
    if state['status'] in ('CLOSED_VERIFIED','REJECTED_NO_POSITION'):
        print(json.dumps({'status':state['status'],'repeatedExecution':False}));return
    assert state['host']==SIM
    assert hashlib.sha256((ROOT/'weex_ai_risk_config.json').read_bytes()).hexdigest()==state['productionConfigSha256']
    read=SimulationGateway(ROOT/'weex_credentials.json').read
    if 'ENTRY' not in state['records']:
        if any(inventory(read)):raise PermissionError('SIMULATION_ACCOUNT_NOT_EMPTY')
        settings=next(r for r in read('get_capi_v3_account_symbolConfig',symbol='BTCUSDT') if r['symbol']=='BTCUSDT')
        assert settings['marginType']=='CROSSED' and D(settings['crossLeverage'])==200
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(state['createdAt'])).total_seconds()
        if not 0<=age<=300:raise PermissionError('CALIBRATION_PLAN_EXPIRED')
        state['status']='EXECUTING';save(state)
        dispatch(state,'ENTRY',state['entry'])
        print(json.dumps({'phase':'ENTRY','dispatchState':state['records']['ENTRY']['state']}),flush=True)
    record=state['records']['ENTRY']
    if record.get('state')=='EXCHANGE_REJECTED' or record.get('response',{}).get('success') is False:
        if any(inventory(read)):raise RuntimeError('REJECTED_BUT_ACCOUNT_NOT_EMPTY')
        state['status']='REJECTED_NO_POSITION';save(state)
        print(json.dumps({'status':state['status'],'errorCode':record.get('errorCode') or record.get('response',{}).get('errorCode')}));return
    row=wait_order(state,'ENTRY',read)
    qty=D(str(row.get('executedQty','0')))
    if qty==0:
        if any(inventory(read)):raise RuntimeError('REJECTED_BUT_ACCOUNT_NOT_EMPTY')
        state['status']='REJECTED_NO_POSITION';save(state);print(json.dumps({'status':state['status']}));return
    if not 0<qty<=D('0.0001'):raise RuntimeError('UNEXPECTED_ENTRY_QUANTITY')
    # Observe margin before immediate close. Do not wait for a favorable price or target profit.
    if 'EXIT' not in state['records']:
        positions=read('get_capi_v3_account_position_allPosition')
        owned=[p for p in positions if p.get('symbol')=='BTCUSDT' and p.get('side')=='LONG']
        if len(positions)!=1 or len(owned)!=1 or D(str(owned[0].get('size','0')))!=qty:
            raise RuntimeError('POSITION_ATTRIBUTION_NOT_CONFIRMED')
        state['positionDuring']=owned[0];state['status']='OPEN_CONFIRMED';save(state)
        close={**state['exitTemplate'],'quantity':format(qty,'f')}
        dispatch(state,'EXIT',close)
    print(json.dumps({'phase':'EXIT','dispatchState':state['records']['EXIT']['state']}),flush=True)
    exit_row=wait_order(state,'EXIT',read)
    if D(str(exit_row.get('executedQty','0')))!=qty:raise RuntimeError('EXIT_QUANTITY_NOT_CONFIRMED')
    p,o,a=inventory(read)
    state['finalInventory']={'positions':len(p),'ordinaryOrders':len(o),'conditionalOrders':len(a)}
    if p or o or a:raise RuntimeError('SIMULATION_ACCOUNT_NOT_EMPTY_AFTER_EXIT')
    state['entryFills']=read('get_capi_v3_userTrades',symbol='BTCUSDT',orderId=row['orderId'],limit=100)
    state['exitFills']=read('get_capi_v3_userTrades',symbol='BTCUSDT',orderId=exit_row['orderId'],limit=100)
    for rows,order in [(state['entryFills'],row),(state['exitFills'],exit_row)]:
        if not isinstance(rows,list) or not rows or len(rows)>=100:raise RuntimeError('FILLS_INCOMPLETE')
        if any(str(t['orderId'])!=str(order['orderId']) or t['symbol']!='BTCUSDT' for t in rows):raise RuntimeError('FILL_OWNERSHIP_MISMATCH')
        if sum(D(str(t['qty'])) for t in rows)!=qty:raise RuntimeError('FILL_QUANTITY_MISMATCH')
    assert hashlib.sha256((ROOT/'weex_ai_risk_config.json').read_bytes()).hexdigest()==state['productionConfigSha256']
    state['status']='CLOSED_VERIFIED';state['finishedAt']=datetime.now(timezone.utc).isoformat();save(state)
    print(json.dumps({'status':state['status'],'quantity':str(qty),'finalInventory':state['finalInventory'],'productionConfigUnchanged':True}))

if __name__=='__main__':
    try:
        if sys.argv[1:] == ['prepare']:prepare()
        elif sys.argv[1:] == ['execute-authorized']:execute()
        else:raise PermissionError('EXPLICIT_CALIBRATION_COMMAND_REQUIRED')
    except Exception as exc:
        print(json.dumps({'status':'REVIEW_REQUIRED','errorType':type(exc).__name__,
            'reason':str(exc) if type(exc) in (RuntimeError,PermissionError,ValueError) else 'SEE_DURABLE_JOURNAL'}))
        raise SystemExit(1)
