"""User-activated strategy worker. Defaults off; offline tests never use the network.

Separate live journal and switch, unchanged PRETRADE scanner. Final HTTP entry
authorization is serialized with the user's STOP. Only attributable TP/remainder
recovery may continue while stopped. This module has no start/arm CLI command.
"""
import copy,hashlib,json,sqlite3,time
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
import live_control as control
from weex_lifecycle import Lifecycle as BaseLifecycle,now
from weex_execution_cycle import exclusive
from weex_execution_readonly import pages
from weex_capacity import account_capacity,full_closing_tp,lifecycle_position_ids
from weex_simple_bot import make_client,public,preview,read as client_read
from weex_http_guard import sdk_types,HttpReadOnlySession,prepare_sdk_request
from market_agents import analyze,trend_matches
from market_agents_rotating import apply_book_gate
from orderbook_liquidity import inspect
from weex_api_budget import budget, recovery, request as budget_request, BudgetDeferred

ROOT=Path(__file__).resolve().parent
HOST='https://api-contract.weex.com'
SCOPE='USER_ACTIVATED_LIVE_V1'

def save(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)

def trailing(root=ROOT):
    from weex_common.transport import RestTransport
    config,_,_=sdk_types();cred=json.loads((Path(root)/'weex_credentials.json').read_text(encoding='utf-8'))
    session=HttpReadOnlySession();session._paths=session._paths|{'/capi/v3/trailing/openOrders'}
    op={'auth':True,'method':'GET','path':'/capi/v3/trailing/openOrders','body_fields':[],
        'query_fields':['symbol','orderId','startTime','endTime','limit','page'],'service':'Trade'}
    transport=RestTransport(config(base_path=HOST,api_key=cred['api_key'],api_secret=cred['secret_key'],
        passphrase=cred['passphrase'],session=session,timeout=10,max_retries=0),{'trailing':op})
    def read(op,**q):
        r=transport.execute('trailing',{'query':q})
        if r.status_code!=200:raise ValueError('TRAILING_READ_FAILED')
        return r.data
    try:return pages(read,'trailing',identity='orderId',start=0)
    finally:session.close()

class Reader:
    def __init__(self,root=ROOT):self.root=Path(root);self.client=make_client()
    def read(self,op,**q):return client_read(self.client,op,**q)
    def account(self):
        started=now()
        jobs=[lambda:self.read('get_capi_v3_account_position_allPosition'),
              lambda:pages(self.read,'get_capi_v3_openOrders',identity='orderId',start=0),
              lambda:pages(self.read,'get_capi_v3_openAlgoOrders',identity='algoId',start=1),lambda:trailing(self.root)]
        with ThreadPoolExecutor(4) as pool:
            def urgent(fn):
                with recovery():return fn()
            fs=[pool.submit(urgent,f) for f in jobs];p,o,a,t=[f.result() for f in fs]
        if not all(isinstance(x,list) for x in (p,o,a,t)):raise ValueError('ACCOUNT_SCHEMA')
        from weex_account_observation import publish
        publish(self.root,started,p,o,a,t)
        a,self.excluded_demo_ids=exclude_verified_demo_aliases(a,p,self.root)
        from weex_trailing import merge,TYPES
        # Deduplicate the same trailing order if regular/openAlgo also lists it.
        ids={str(x['orderId']) for x in t}
        o=[x for x in o if not (str(x.get('orderId')) in ids and x.get('type') in TYPES)]
        return p,o,merge(a,t)
    def diagnostic_account(self):
        from weex_account_observation import load
        data=load(self.root,max_age=5)
        if data is None:return self.account()
        p=data['positions'];a,self.excluded_demo_ids=exclude_verified_demo_aliases(data['conditionalOrders'],p,self.root)
        from weex_trailing import merge,TYPES
        t=data['trailingOrders'];ids={str(x['orderId']) for x in t}
        o=[x for x in data['regularOrders'] if not (str(x.get('orderId')) in ids and x.get('type') in TYPES)]
        return p,o,merge(a,t)

def exclude_verified_demo_aliases(algos,positions,root):
    """Only immutable IDs independently observed as full demo TPs; no suffix guessing."""
    try:
        proof=json.loads((Path(root)/'live_demo_alias_proof.json').read_text(encoding='utf-8'))
        if proof.get('verifiedAgainst')!='https://api-sim.weex.com' or proof.get('liveSource')!=HOST:return algos,[]
        known=proof['orders']
    except (OSError,ValueError,KeyError,TypeError):return algos,[]
    kept=[];excluded=[]
    fields=('algoId','clientAlgoId','symbol','side','positionSide','quantity','triggerPrice','workingType','reduceOnly','closePosition','algoStatus')
    for a in algos:
        if (a.get('orderType')=='TAKE_PROFIT_MARKET' and a.get('reduceOnly') is True
            and not any(p['symbol']==a['symbol'] for p in positions)
            and any(all(a.get(k)==r.get(k) for k in fields) for r in known)):
            excluded.append(str(a['algoId']))
        else:kept.append(a)
    return kept,excluded

def capacity(rows, root=ROOT, *, notify_missing=True):
    p,o,a=rows
    import weex_manual_position_ack
    apply_fresh_observation=weex_manual_position_ack.apply_fresh_observation
    notify=weex_manual_position_ack.notify
    acknowledged=apply_fresh_observation(root,p)
    missing=[position for position in p if not any(full_closing_tp(tp,[position]) for tp in a)
             and weex_manual_position_ack.key(position) not in acknowledged]
    if missing:
        if notify_missing:
            try:notify(root,missing)
            except Exception:pass
        raise ValueError('EXISTING_POSITION_WITHOUT_FULL_TP:'+','.join(sorted({x['symbol'] for x in missing})))
    managed_ids=lifecycle_position_ids(Path(root)/'weex_user_live_lifecycle.sqlite3')
    # Classification is informational, never a new-entry permit. The existing
    # account-wide CROSS collateral guardian is deliberately left intact.
    from weex_multi_symbol_ownership_v12 import classify
    ownership=classify(root,p,o,a)
    result=account_capacity(p,o+a,managed_position_ids=managed_ids)
    result['ownershipAudit']=ownership
    return result

def eligible(signal):
    if not 0<=time.time()-datetime.fromisoformat(signal['observedAt']).timestamp()<=60:raise ValueError('SIGNAL_STALE')
    for tf,ms in (('5m',300000),('15m',900000),('1h',3600000)):
        if not 0<=now()-int(signal['closedCandleTimes'][tf])<=ms+10000:raise ValueError('CANDLES_NOT_CLOSED_OR_CURRENT')
    side=signal.get('decision')
    return (trend_matches(signal['trend'],side) and signal['momentum']['confirmed'] is True)

def capture(reader,symbol,cfg,*,manual_side=None,manual_request_id=None,notify_missing_tp=True):
    if manual_side is not None:
        from weex_trading_modes import normalize_side
        manual_side=normalize_side(manual_side)
    start=now()
    trailing_mode=cfg['strategySettings'].get('tpMode')=='trailing'
    jobs={'signal':lambda:analyze(symbol) if manual_side is None or trailing_mode else
              {'symbol':symbol,'decision':manual_side,'reasons':[],'closedCandleTimes':None},
        'book':lambda:inspect(symbol),
        'meta':lambda:public('/capi/v3/market/exchangeInfo',symbol=symbol),
        'tiers':lambda:public('/capi/v3/market/riskLimits',symbol=symbol),
        'allowed':lambda:public('/capi/v3/market/apiTradingSymbols'),
        'rows':reader.account,'fees':lambda:reader.read('get_capi_v3_account_commissionRate',symbol=symbol),
        'settings':lambda:reader.read('get_capi_v3_account_symbolConfig',symbol=symbol),
        'account':lambda:reader.read('get_capi_v3_account_accountConfig'),
        'balances':lambda:reader.read('get_capi_v3_account_balance')}
    with ThreadPoolExecutor(12) as pool:
        fs={k:pool.submit(fn) for k,fn in jobs.items()};data={k:f.result() for k,f in fs.items()}
    if not 0<=now()-start<=5000:raise ValueError('STALE_PREFLIGHT')
    signal=data['signal']
    if manual_side is None:
        if not eligible(signal):raise ValueError('NO_CONFIRMED_SIGNAL')
    else:
        # The Telegram command supplies the side and replaces strategy signals.
        # Time-sensitive account, book, fee, leverage, and TP gates still apply.
        signal={**signal,'decision':manual_side}
    market=apply_book_gate(signal,data['book']);book=market['realOrderBook']
    from weex_trading_modes import validate_entry_book
    validate_entry_book(book,manual_override=manual_side is not None)
    meta=next(m for m in data['meta']['symbols'] if m['symbol']==symbol)
    if meta.get('forwardContractFlag') is not True:raise ValueError('LIVE_CONTRACT_SETTLEMENT_UNVERIFIED')
    setting=next(r for r in data['settings'] if r['symbol']==symbol)
    if setting.get('separatedType')!='COMBINED':raise ValueError('COMBINED_ACCOUNT_MODE_REQUIRED')
    fees=data['fees']
    if isinstance(fees,list):fees=next(f for f in fees if f['symbol']==symbol)
    tiers=next(t['brackets'] for t in data['tiers'] if t['symbol']==symbol)
    balance=next(b['availableBalance'] for b in data['balances'] if b['asset']=='USDT')
    plan=preview(market,meta,setting,cfg,commission=fees,brackets=tiers,available_balance=balance,
                 manual_override=manual_side is not None)
    if plan.get('status')!='BLOCKED_PREVIEW':raise ValueError('NO_EXECUTABLE_PLAN')
    p,o,a=data['rows'];cap=capacity(data['rows'],reader.root,notify_missing=notify_missing_tp)
    if manual_side is None and cap['count']>=cfg['telegramSettings']['maxConcurrentPositions']['default']:
        raise ValueError('CAPACITY')
    source='manual_telegram' if manual_side is not None else 'automatic'
    plan.update(beforePositions=p,closedCandleTimes=signal.get('closedCandleTimes'),strategySignalUsed=manual_side is None,
        entrySource=source,liveAuthorizationScope=SCOPE,
        tpAccountingMode=cfg['strategySettings'].get('tpAccountingMode','NET'))
    if trailing_mode:
        from weex_trailing import entry_policy
        plan['exitPolicy']=entry_policy(data['signal'],cfg['strategySettings']['targetNetProfitUSDT'])
    if manual_request_id is not None:plan['manualRequestId']=str(manual_request_id)
    ctx={'observedAtMs':start,'complete':True,'apiEnabled':symbol in data['allowed'],
        'accountCanTrade':data['account'].get('canTrade'),'hedgeMode':data['account'].get('dualSidePosition'),
        'depthUnitVerified':book.get('depthUnitVerified') is True,'liquidityPassed':book.get('passed') is True,
        'marketDataValid':book.get('status')=='OK','riskTierVerified':plan['publicRiskTierVerified'],
        'marketSignal':signal['decision'],'closedCandleTimes':signal['closedCandleTimes'],
        'availableBalance':balance,'maximumPermittedLeverage':plan['requestedLeverage'],
        'positions':p,'openOrders':o,'conditionalOrders':a,'symbolConfig':setting,
        'referencePrice':book['bestAsk' if signal['decision']=='LONG' else 'bestBid'],'exitFeeRate':plan['exitFeeRate']}
    return plan,ctx,signal

class Lifecycle(BaseLifecycle):
    def fills(self,order,trades):
        result=super().fills(order,trades)
        if abs(D(order['cumQuote'])-result[1])>D('.00000001'):raise ValueError('ORDER_QUOTE_MISMATCH')
        for t in trades:
            if abs(D(t['quoteQty'])-D(t['qty'])*D(t['price']))>D('.00000001'):raise ValueError('FILL_QUOTE_MISMATCH')
        return result
    def entry_fills(self,item,order,trades,positions):
        """Use current fills or exact persisted evidence from the original entry."""
        try:return self.fills(order,trades),None
        except ValueError as exc:
            if str(exc)=='FILL_TOTAL_MISMATCH' and isinstance(trades,list):
                owned=item.get('owned') or {}
                proof=owned.get('entryFillEvidence') or {}
                raw=proof.get('rawOrder') or {}
                saved=proof.get('fills')
                if proof.get('method')!='FILLS_POSITION_EXACT_V1' or not isinstance(saved,list) or not saved:
                    raise ValueError('PERSISTED_ENTRY_PROOF_UNAVAILABLE') from None
                fields=('orderId','clientOrderId','symbol','side','positionSide','type','status',
                        'origQty','executedQty','avgPrice','cumQuote','time')
                if any(order.get(k)!=raw.get(k) for k in fields):
                    raise ValueError('PERSISTED_ENTRY_ORDER_CHANGED')
                if (str(proof.get('orderId'))!=str(order.get('orderId'))
                        or str(proof.get('positionId'))!=str(owned.get('positionId'))
                        or str(order.get('clientOrderId'))!=str(item.get('id'))
                        or order.get('status')!='FILLED' or order.get('type')!='MARKET'):
                    raise ValueError('PERSISTED_ENTRY_BINDING')
                fill_fields=('id','orderId','symbol','side','positionSide','qty','price','quoteQty',
                             'commission','commissionAsset','time')
                try:canonical=sorted([{k:t[k] for k in fill_fields} for t in saved],key=lambda t:str(t['id']))
                except (KeyError,TypeError):raise ValueError('PERSISTED_ENTRY_FILL_SCHEMA') from None
                digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                if digest!=proof.get('fillsDigest'):raise ValueError('PERSISTED_ENTRY_DIGEST_MISMATCH')
                if len(trades)>=len(canonical):raise ValueError('PERSISTED_ENTRY_NOT_A_PARTIAL_HISTORY')
                by_id={str(t['id']):t for t in canonical}
                try:observed=[{k:t[k] for k in fill_fields} for t in trades]
                except (KeyError,TypeError):raise ValueError('CURRENT_ENTRY_FILL_SCHEMA') from None
                if any(by_id.get(str(t['id']))!=t for t in observed) or len({str(t['id']) for t in observed})!=len(observed):
                    raise ValueError('CURRENT_ENTRY_FILL_CONTRADICTS_PROOF')
                for t in canonical:
                    if D(t['quoteQty'])!=D(t['qty'])*D(t['price']):
                        raise ValueError('PERSISTED_ENTRY_QUOTE_MISMATCH')
                result=BaseLifecycle.fills(self,order,canonical)
                qty,cost,fees=result
                if (qty!=D(owned.get('quantity')) or cost!=D(owned.get('actualEntryCostUSDT'))
                        or fees!=D(owned.get('actualEntryFeesUSDT'))):
                    raise ValueError('PERSISTED_ENTRY_ECONOMICS_MISMATCH')
                return result,proof
            if str(exc)!='ORDER_QUOTE_MISMATCH':raise
        result=BaseLifecycle.fills(self,order,trades);qty,cost,fees=result
        for t in trades:
            if D(t['quoteQty'])!=D(t['qty'])*D(t['price']):raise ValueError('FILL_QUOTE_MISMATCH')
        entry=item['plan']['entry']
        if (order.get('status')!='FILLED' or order.get('type')!='MARKET'
                or order.get('reduceOnly') is not False
                or order.get('clientOrderId')!=item['id']
                or any(order.get(k)!=entry[k] for k in ('symbol','side','positionSide'))
                or qty!=D(entry['quantity']) or qty!=D(order['origQty'])
                or len({D(t['price']) for t in trades})<2
                or D(order['avgPrice']) not in {D(t['price']) for t in trades}
                or D(order['cumQuote'])!=qty*D(order['avgPrice'])):
            raise ValueError('ORDER_QUOTE_MISMATCH_UNCORROBORATED')
        fields=('id','orderId','symbol','side','positionSide','qty','price','quoteQty','commission','commissionAsset','time')
        canonical=sorted([{k:t[k] for k in fields} for t in trades],key=lambda t:str(t['id']))
        digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        owned=item.get('owned')
        if owned:
            proof=owned.get('entryFillEvidence') or {}
            if (proof.get('method')!='FILLS_POSITION_EXACT_V1' or proof.get('fillsDigest')!=digest
                    or proof.get('orderId')!=str(order['orderId']) or proof.get('positionId')!=owned['positionId']
                    or qty!=D(owned['quantity']) or cost!=D(owned['actualEntryCostUSDT'])
                    or fees!=D(owned['actualEntryFeesUSDT'])):
                raise ValueError('ENTRY_CORROBORATION_CHANGED')
            return result,proof
        own=[p for p in positions if p['symbol']==item['symbol']]
        if len(own)!=1:raise ValueError('ENTRY_POSITION_CORROBORATION_REQUIRED')
        p=own[0]
        if (not p.get('id') or p.get('side')!=entry['positionSide'] or p.get('asset')!='USDT'
                or p.get('marginType')!='CROSSED' or p.get('separatedMode')!='COMBINED'
                or any(D(p[k])!=qty for k in ('size','cumOpenSize'))
                or any(D(p[k])!=cost for k in ('openValue','cumOpenValue'))
                or any(D(p[k])!=fees for k in ('openFee','cumOpenFee'))
                or any(D(p[k])!=0 for k in ('cumCloseSize','cumCloseValue','cumCloseFee'))
                or not int(order['time'])<=int(p['createdTime'])<=max(int(t['time']) for t in trades)
                or any(int(t['time'])<int(p['createdTime']) for t in trades)):
            raise ValueError('ENTRY_POSITION_ECONOMICS_MISMATCH')
        proof={'method':'FILLS_POSITION_EXACT_V1','observedAtMs':now(),'orderId':str(order['orderId']),
               'positionId':str(p['id']),'fillsDigest':digest,'rawOrder':copy.deepcopy(order),
               'fills':canonical,'position':copy.deepcopy(p)}
        return result,proof

    def observations(self,item):
        # Same validator, parallel independent reads to retain the five-second bound.
        start=now();original=self.gateway;ack=self.writes(item['id']).get('ENTRY',{}).get('response') or {}
        if not isinstance(ack,dict) or not ack.get('orderId'):return super().observations(item)
        s=item['symbol'];oid=ack['orderId']
        req=[('get_capi_v3_openOrders',{'page':0,'limit':100,'symbol':s}),('get_capi_v3_order',{'orderId':oid}),
            ('get_capi_v3_userTrades',{'symbol':s,'orderId':oid,'limit':100}),('get_capi_v3_account_position_allPosition',{}),
            ('get_capi_v3_openAlgoOrders',{'page':1,'limit':100,'symbol':s}),
            ('get_capi_v3_allAlgoOrders',{'symbol':s,'startTime':item['created']-1000,'endTime':start,'limit':1000})]
        from weex_trailing import is_trailing,OPEN_OPERATION,HISTORY_OPERATION
        if is_trailing(item['plan']):
            req.extend([(OPEN_OPERATION,{'page':0,'limit':100,'symbol':s}),
                        (HISTORY_OPERATION,{'page':0,'limit':100,'symbol':s,'startTime':item['created']-1000,'endTime':start})])
        def key(op,q):return op,json.dumps({k:str(v) for k,v in q.items() if k!='endTime'},sort_keys=True)
        with ThreadPoolExecutor(len(req)) as pool:
            fs=[(op,q,pool.submit(original.read,op,**q)) for op,q in req]
            cache={key(op,q):f.result() for op,q,f in fs}
        class Snapshot:
            def read(self,op,**q):return copy.deepcopy(cache[key(op,q)]) if key(op,q) in cache else original.read(op,**q)
        self.gateway=Snapshot()
        try:
            result=super().observations(item)
            if now()-start>5000:raise ValueError('SNAPSHOT_TOO_SLOW')
            return result
        finally:self.gateway=original

class Gateway:
    def __init__(self,root,reader):self.root=Path(root);self.reader=reader;self.engine=None;self.current=None;self.ctx=None
    def repair_preview(self,trade_id,operation,payload):
        """Validate an immutable TP repair intent without any network submission."""
        from weex_tp_repair_gateway_binding import validate
        return validate(self.root,trade_id,operation,payload)
    def read(self,op,**q):
        with recovery():return self.reader.read(op,**q)
    def validate(self,op,p):
        if not self.current:raise PermissionError('NO_OWNED_INTENT')
        item=self.engine.get(self.current);plan=item['plan'];auth=plan.get('authorization') or {}
        if plan.get('liveAuthorizationScope')!=SCOPE or auth.get('host')!=HOST:raise PermissionError('LIVE_SCOPE_REQUIRED')
        requests={'ENTRY':('post_capi_v3_order',plan['entry']),
                  'MARGIN':(plan['setupRequests'][0]['operation'],plan['setupRequests'][0]['payload']),
                  'LEVERAGE':(plan['setupRequests'][1]['operation'],plan['setupRequests'][1]['payload'])}
        if item['owned']:
            requests['TP']=(item['owned'].get('tpOperation','post_capi_v3_placeTpSlOrder'),item['owned']['tpRequest'])
            if 'TP_REPAIR' in self.engine.writes(item['id']):
                requests['TP_REPAIR']=requests.pop('TP')
        if op=='delete_capi_v3_order':
            order=self.read('get_capi_v3_order',orderId=p['query']['orderId'])
            if order.get('clientOrderId')!=item['id'] or order.get('symbol')!=item['symbol']:raise PermissionError('CANCEL_OWNERSHIP')
            requests['CANCEL_REMAINDER']=(op,{'query':{'orderId':order['orderId']}})
        kinds=[k for k,v in requests.items() if v==(op,p)]
        if len(kinds)!=1:raise PermissionError('EXACT_OWNED_REQUEST_REQUIRED')
        kind=kinds[0];record=self.engine.writes(item['id']).get(kind)
        if not record or record['state']!='UNKNOWN' or record['payload']!=p:raise PermissionError('DURABLE_UNKNOWN_INTENT_REQUIRED')
        if kind=='TP_REPAIR':
            from weex_tp_local_notsent_repair import marker as local_notsent
            prior=self.engine.writes(item['id']).get('TP',{})
            if (not local_notsent(prior.get('response')) or prior.get('state')!='RESPONSE_RECEIVED'
                    or prior.get('operation')!=op or prior.get('payload')!=p):
                raise PermissionError('TP_REPAIR_PRIOR_NON_SUBMISSION_NOT_PROVEN')
        if kind in ('ENTRY','MARGIN','LEVERAGE'):
            from weex_trading_modes import get_mode
            if get_mode(self.root)['mode']=='manual_only' and plan.get('entrySource')!='manual_telegram':
                raise PermissionError('AUTOMATIC_ENTRY_DISABLED_IN_MANUAL_MODE')
            if self.ctx is None:raise PermissionError('FRESH_ENTRY_CONTEXT_REQUIRED')
            self.engine.guard(item,self.ctx)
        return kind,auth
    def write(self,op,p):
        self._network_started=False
        try:return self._write(op,p)
        except Exception:
            if self._network_started:raise
            failure={'success':False,'localNotSent':True,'reason':'BLOCKED_BEFORE_NETWORK'}
            return [failure] if op=='post_capi_v3_placeTpSlOrder' else failure
    def _write(self,op,p):
        kind,auth=self.validate(op,p);config,contract,ops=sdk_types();spec=ops[op]
        if spec['method']=='POST':prepare_sdk_request(op,p)
        gateway=self;network_started=False
        class Transport:
            used=False
            def request(self,method,url,**kw):
                nonlocal network_started
                expected=HOST+spec['path']
                if method=='DELETE':expected+='?orderId='+str(p['query']['orderId'])
                if (self.used or method!=spec['method'] or url!=expected or kw.get('json') is not None or kw.get('params')
                    or (method=='POST' and json.loads(kw.get('data',b'{}'))!=p)
                    or (method=='DELETE' and kw.get('data') not in (None,'',b''))):raise PermissionError('EXACT_LIVE_REQUEST_REQUIRED')
                gateway.validate(op,p);self.used=True
                from contextlib import nullcontext
                permit=(control.dispatch_permission(gateway.root,auth['generation'],auth['configHash'])
                        if kind in ('ENTRY','MARGIN','LEVERAGE') else nullcontext())
                with permit:
                    import requests
                    with requests.Session() as network:
                        kw['allow_redirects']=False
                        if kind=='ENTRY':budget().require_entry_headroom()
                        # Reserve before flagging an uncertain network dispatch.
                        with recovery():budget().reserve(method,url)
                        network_started=True;gateway._network_started=True;r=network.request(method,url,**kw)
                        budget().observe(r.status_code,r.headers)
                        if 300<=r.status_code<400:raise PermissionError('REDIRECT_BLOCKED')
                        return r
            def close(self):pass
        cred=json.loads((self.root/'weex_credentials.json').read_text(encoding='utf-8'))
        client=contract(config_rest_api=config(base_path=HOST,api_key=cred['api_key'],api_secret=cred['secret_key'],
            passphrase=cred['passphrase'],session=Transport(),max_retries=0,timeout=10))
        try:r=client.rest_api.execute_operation(op,p)
        except Exception:
            if not network_started:
                result={'success':False,'localNotSent':True,'reason':'BLOCKED_BEFORE_NETWORK'}
                return [result] if op=='post_capi_v3_placeTpSlOrder' else result
            raise
        if r.status_code!=200:raise RuntimeError('DISPATCH_UNCERTAIN_READBACK_REQUIRED')
        return r.data

def protected_unchanged(engine,tid,rows,observed_at):
    """Skip old fills/history only with fresh, complete, exact position/TP evidence.

    A missing/changed position or TP always falls back to full reconciliation.
    This function never concludes that a position closed or sends an order.
    """
    try:
        if not 0<=now()-observed_at<=5000:return False
        item=engine.get(tid);owned=item.get('owned');writes=engine.writes(tid)
        from weex_trailing import is_trailing,matches_request
        trailing_exit=is_trailing(item['plan'])
        if item['state']!='PROTECTED' or not owned or 'ENTRY' not in writes or 'TP' not in writes:return False
        positions,orders,algos=rows
        if any(not isinstance(group,list) or any(not isinstance(x,dict) or not x.get('symbol') for x in group) for group in rows):return False
        own=[p for p in positions if p['symbol']==item['symbol']]
        active=[a for a in algos if a['symbol']==item['symbol']]
        if len(own)!=1 or len(active)!=1 or any(o['symbol']==item['symbol'] for o in orders):return False
        p=own[0];a=active[0];tp=owned['tpRequest'];qty=D(owned['quantity'])
        if not qty.is_finite() or qty<=0:return False
        if (str(p.get('id'))!=owned['positionId'] or p.get('side')!=tp['positionSide']
                or D(str(p['size']))!=qty):return False
        for field,key in (('openValue','actualEntryCostUSDT'),('openFee','actualEntryFeesUSDT')):
            if field in p and D(str(p[field]))!=D(owned[key]):return False
        if str(a.get('algoId'))!=str(item['detail']['tpId']):return False
        if trailing_exit:
            if a.get('algoStatus') not in ('NEW','UNTRIGGERED') or not matches_request(a,tp):return False
        elif (a.get('clientAlgoId')!=tp['clientAlgoId']
                or a.get('symbol')!=item['symbol'] or a.get('positionSide')!=tp['positionSide']
                or a.get('side')!=('SELL' if tp['positionSide']=='LONG' else 'BUY')
                or a.get('orderType')!='TAKE_PROFIT_MARKET' or a.get('algoStatus') not in ('NEW','UNTRIGGERED')
                or a.get('reduceOnly') is not True or a.get('closePosition')!=tp.get('closePosition')
                or a.get('workingType')!=tp['triggerPriceType'] or D(str(a['quantity']))!=qty
                or D(str(a['triggerPrice']))!=D(tp['triggerPrice'])):return False
        from weex_tp_local_notsent_repair import marker as tp_local_notsent
        if tp_local_notsent(writes['TP'].get('response')) and 'TP_REPAIR' not in writes:return False
        response=(writes['TP_REPAIR'] if 'TP_REPAIR' in writes and tp_local_notsent(writes['TP'].get('response'))
                  else writes['TP']).get('response')
        if isinstance(response,dict):response=[response]
        if isinstance(response,list) and len(response)==1:
            if response[0].get('success') is False:return False
            if response[0].get('orderId') and str(response[0]['orderId'])!=str(a['algoId']):return False
        return True
    except (ValueError,KeyError,TypeError,ArithmeticError):return False


def report(root,status,**fields):
    r={'checkedAt':control.timestamp(),'host':HOST,'status':status,'control':control.state(root),
       'accountReadOK':False,'recoveryClear':False,**fields}
    save(Path(root)/'weex_live_worker_latest.json',r)
    with (Path(root)/'weex_live_worker_events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\n')
    print(json.dumps({k:r[k] for k in ('checkedAt','status','control')}),flush=True)
    return r

def candidates(root):
    scan=json.loads((Path(root)/'weex_simple_bot_latest.json').read_text(encoding='utf-8'))
    age=time.time()-datetime.fromisoformat(scan['checkedAt']).timestamp()
    if not 0<=age<=720 or scan.get('ordersSubmitted') is not False:raise ValueError('SCAN_STALE_OR_INVALID')
    universe={s['symbol'] for s in json.loads((Path(root)/'universe_latest.json').read_text(encoding='utf-8'))['symbols']}
    rows=[r for r in scan['results'] if r.get('symbol') in universe and r.get('marketSignal') in ('LONG','SHORT')
        and (r.get('realOrderBook') or {}).get('passed') is True and (r.get('realOrderBook') or {}).get('depthUnitVerified') is True]
    return sorted(rows,key=lambda r:r.get('momentum',{}).get('volumeRatio',0),reverse=True)

def run(root=ROOT,reader=None,gateway_factory=Gateway,capture_fn=capture,*,manual_only=False,manual_request_id=None):
    root=Path(root);started=time.monotonic()
    with exclusive(root/'weex_live_worker.lock'):
        try:
            configuration_error=None
            try:cfg,digest=control.configuration(root)
            except Exception as exc:
                configuration_error=str(exc) if type(exc) is ValueError else 'CONFIG_INVALID'
                cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'));digest=None
            reader=reader or Reader(root);gateway=gateway_factory(root,reader)
            current_cfg=copy.deepcopy(cfg)
            def engine_config():
                # The controlled gateway is the final authority. TP recovery must
                # remain possible after STOP, without allowing any new entry.
                x=copy.deepcopy(current_cfg);x['execution'].update(enabled=True,mode='LIVE');return x
            engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',gateway,engine_config);gateway.engine=engine
            recovered=[];opened=[];attempts=[];skipped=[]
            snapshot=None;snapshot_at=0
            def account_snapshot():
                # Propagate recovery priority into the independent account jobs.
                with recovery():return reader.diagnostic_account() if hasattr(reader,'diagnostic_account') else reader.account()
            def reconcile(tid):
                gateway.current=tid
                for _ in range(3):
                    r=engine.reconcile(tid)
                    if r['state'] not in ('ENTRY_PENDING','ENTRY_FILLED','TP_PENDING'):break
                    time.sleep(.4)
                return {'tradeId':tid,'state':r['state'],'detail':r.get('detail')}
            for item in engine.states():
                if item['state'] in ('CLOSED','REJECTED','SUPERSEDED'):continue
                if not engine.writes(item['id']).get('ENTRY'):
                    # The entry intent is always committed before dispatch. A
                    # setup-only attempt cannot have opened a position.
                    engine.state(item['id'],'SUPERSEDED',{'reason':'PREVIOUS_CYCLE_NO_ENTRY_DISPATCH'})
                    continue
                if item['state']=='PROTECTED':
                    try:
                        if snapshot is None or now()-snapshot_at>5000:
                            snapshot_at=now();snapshot=account_snapshot()
                        if protected_unchanged(engine,item['id'],snapshot,snapshot_at):
                            recovered.append({'tradeId':item['id'],'state':'PROTECTED','detail':{'verification':'SHARED_ACCOUNT_SNAPSHOT'}})
                            continue
                    except Exception:
                        snapshot=None
                # External manual TP adoption is evidence-only. It never impersonates
                # a bot TP dispatch and never authorizes a new LIVE entry by itself.
                adopted=None
                if item['state']=='REVIEW_REQUIRED':
                    try:
                        from weex_external_tp_adoption import verify,save_evidence
                        if snapshot is None or now()-snapshot_at>5000:
                            snapshot=account_snapshot();snapshot_at=now()
                        proof=verify(root,item['id'],snapshot,snapshot_at)
                        save_evidence(root,proof)
                        adopted={'tradeId':item['id'],'state':'PROTECTED_EXTERNAL',
                                 'detail':{'verification':'EXTERNAL_MANUAL_TP','evidenceSha256':proof['sha256']}}
                    except (ValueError,KeyError,TypeError,ArithmeticError,sqlite3.Error,OSError):
                        adopted=None
                if adopted is not None:
                    recovered.append(adopted)
                else:
                    recovered.append(reconcile(item['id']))
                snapshot=None
            clear=all(r['state'] in ('CLOSED','REJECTED','PROTECTED','PROTECTED_EXTERNAL') for r in recovered)
            rows=snapshot if snapshot is not None and 0<=now()-snapshot_at<=5000 else account_snapshot();cap=capacity(rows,root)
            base={'accountReadOK':True,'recoveryClear':clear,'capacity':cap,'recovered':recovered,'opened':opened,'entryAttempts':attempts,'skipped':skipped,
                  'excludedVerifiedDemoOrderIds':getattr(reader,'excluded_demo_ids',[])}
            from weex_trading_modes import cancel_pending_manual
            # Independent, read-only veto for any UNKNOWN entry still unresolved
            # after the existing worker's TP/position recovery. Never retry a
            # potentially dispatched entry and never treat an audit as permission.
            try:
                from weex_worker_recovery_readonly_20261109 import worker_uncertain_entry_guard
                entry_recovery_audit=worker_uncertain_entry_guard(root,reader)
            except Exception as exc:
                entry_recovery_audit={'passNewEntries':False,'uncertainCount':None,
                    'cases':[],'readOnly':True,'newExchangeWrites':0,
                    'reason':'RECOVERY_AUDIT_FAILED_'+type(exc).__name__}
            base['entryRecoveryAudit']=entry_recovery_audit
            if entry_recovery_audit.get('passNewEntries') is not True:
                cancel_pending_manual(root,'BLOCKED_UNKNOWN_ENTRY_AUDIT')
                return report(root,'BLOCKED_UNKNOWN_ENTRY_AUDIT',
                              recoveryClear=False,**{k:v for k,v in base.items() if k!='recoveryClear'})
            if not clear:
                cancel_pending_manual(root,'BLOCKED_RECOVERY')
                return report(root,'BLOCKED_RECOVERY',**base)
            if configuration_error:
                cancel_pending_manual(root,'BLOCKED_CONFIG')
                return report(root,'BLOCKED_CONFIG',reason=configuration_error,**base)
            # Trading mode is an independent entry gate. Recovery and TP management above
            # still run in every mode; alerts_only must never dispatch a new entry.
            from weex_trading_modes import get_mode
            trading_mode=get_mode(root)['mode']
            base['tradingMode']=trading_mode
            if trading_mode=='alerts_only':
                cancel_pending_manual(root,'ALERTS_ONLY')
                return report(root,'ALERTS_ONLY',**base)
            sw=control.state(root)
            if sw['mode']!='RUNNING':
                cancel_pending_manual(root,'LIVE_SWITCH_STOPPED')
                return report(root,'DISARMED_READY',**base)
            # In manual-only mode with no pending entry, this is a monitoring
            # cycle, not a new-entry request. Preserve TP recovery above and
            # avoid misreporting an existing protected position as a blocked
            # NEW entry. Any queued entry still passes the guardian below.
            if trading_mode=='manual_only' and manual_request_id is None:
                from weex_trading_modes import connect as modes_connect
                with closing(modes_connect(root)) as modes_db:
                    waiting=modes_db.execute("SELECT 1 FROM manual_requests_v1 WHERE state='PENDING' LIMIT 1").fetchone()
                if waiting is None:
                    base['manualRequests']=[]
                    return report(root,'WAIT_MANUAL_REQUEST',**base)
            # Mandatory new-entry veto, AFTER prior-position reconciliation.
            # Never disable recoveries already performed above.
            from weex_live_new_entry_guard import evaluate as entry_safety
            safety=entry_safety(cfg,rows[0],rows[1],rows[2])
            if not safety['allowed']:
                cancel_pending_manual(root,'BLOCKED_GUARDIAN_ENTRY')
                return report(root,'BLOCKED_GUARDIAN_ENTRY',
                              guardianIssues=safety['issues'],**base)
            errors=control.build_errors(root)
            if errors:
                cancel_pending_manual(root,'BLOCKED_RELEASE')
                return report(root,'BLOCKED_RELEASE',releaseErrors=errors,**base)
            from weex_trading_modes import claim_next,finish_request
            manual_results=[]
            if trading_mode in ('automatic_manual','manual_only'):
                request=claim_next(root,request_id=manual_request_id)
                if request:
                    signal_id='manual_telegram|'+request['id']
                    tid='wxentry_'+hashlib.sha256(signal_id.encode()).hexdigest()[:24]
                    try:
                        existing={x['id'] for x in engine.states()}
                        if tid in existing:
                            item=engine.get(tid);gateway.current=tid
                            if item['state']=='PROTECTED':
                                result={'state':'PROTECTED','tradeId':tid,'detail':item.get('detail')}
                            elif item['state']=='CLOSED':
                                result={'state':'CLOSED','tradeId':tid,'detail':item.get('detail')}
                            elif item['state'] in ('REJECTED','SUPERSEDED'):
                                result={'state':item['state'],'tradeId':tid,'detail':item.get('detail')}
                            elif engine.writes(tid).get('ENTRY'):
                                result=reconcile(tid)
                            else:
                                plan,ctx,_=capture_fn(reader,request['symbol'],cfg,
                                    manual_side=request['side'],manual_request_id=request['id'])
                                gateway.ctx=ctx
                                def resume_manual(_symbol):
                                    _,fresh,_=capture_fn(reader,request['symbol'],cfg,
                                        manual_side=request['side'],manual_request_id=request['id'])
                                    gateway.ctx=fresh;return fresh
                                result=engine.advance(tid,resume_manual)
                        else:
                            plan,ctx,_=capture_fn(reader,request['symbol'],cfg,
                                manual_side=request['side'],manual_request_id=request['id'])
                            plan['authorization']={'host':HOST,'generation':sw['generation'],'configHash':digest}
                            item=engine.prepare(signal_id,plan);gateway.current=item['id'];gateway.ctx=ctx
                            engine.guard(item,ctx)
                            def refresh_manual(_symbol):
                                _,fresh,_=capture_fn(reader,request['symbol'],cfg,
                                    manual_side=request['side'],manual_request_id=request['id'])
                                gateway.ctx=fresh;return fresh
                            result=engine.advance(item['id'],refresh_manual)
                        if engine.writes(tid).get('ENTRY'):
                            result=reconcile(tid)
                            attempts.append(result)
                            if result.get('state') in ('PROTECTED','CLOSED'):opened.append(result)
                        state=result.get('state')
                        if state=='PROTECTED':final='PROTECTED'
                        elif state=='CLOSED':final='CLOSED'
                        elif state in ('REJECTED','SUPERSEDED','PREFLIGHT_BLOCKED','STOP_BEFORE_SUBMISSION') and not engine.writes(tid).get('ENTRY'):
                            final='REJECTED'
                        elif not engine.writes(tid).get('ENTRY'):
                            final='REJECTED'
                        else:final='REVIEW_REQUIRED'
                        finish_request(root,request['id'],final,{'tradeId':tid,'state':state,'reason':result.get('reason')})
                        manual_results.append({'id':request['id'],'symbol':request['symbol'],'side':request['side'],
                                               'state':final,'tradeState':state,'reason':result.get('reason')})
                    except Exception as exc:
                        sent=engine.writes(tid).get('ENTRY') if tid in {x['id'] for x in engine.states()} else None
                        final='REVIEW_REQUIRED' if sent else 'REJECTED'
                        finish_request(root,request['id'],final,{'tradeId':tid,'errorType':type(exc).__name__})
                        manual_results.append({'id':request['id'],'symbol':request['symbol'],'side':request['side'],
                                               'state':final,'reason':str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__})
                elif manual_request_id:
                    base['manualRequests']=manual_results
                    return report(root,'MANUAL_REQUEST_NOT_AVAILABLE',**base)
            base['manualRequests']=manual_results
            if manual_only or trading_mode=='manual_only':
                status='MANUAL_PROTECTED' if any(x['state']=='PROTECTED' for x in manual_results) else 'MANUAL_REVIEW_REQUIRED' if any(x['state']=='REVIEW_REQUIRED' for x in manual_results) else 'MANUAL_REJECTED' if manual_results or manual_request_id else 'WAIT_MANUAL_REQUEST'
                return report(root,status,**base)
            if cap['count']>=cfg['telegramSettings']['maxConcurrentPositions']['default']:return report(root,'WAIT_CAPACITY',**base)
            for row in candidates(root):
                if len(attempts)>=3 or time.monotonic()-started>110:break
                symbol=row['symbol']
                if any(r['symbol']==symbol for group in rows for r in group):continue
                try:
                    budget().require_entry_headroom()
                    plan,ctx,signal=capture_fn(reader,symbol,cfg)
                    # The scan is a shortlist, not the entry plan. capture() has
                    # just rebuilt the complete plan from current closed candles.
                    # A newer candle is valid if it still confirms the direction;
                    # the lifecycle binds this NEW plan to its exact candle times
                    # and rejects another change before dispatch.
                    if signal['decision']!=row['marketSignal'] or any(
                        int(signal['closedCandleTimes'][tf])<int(row['closedCandleTimes'][tf]) for tf in ('5m','15m','1h')):
                        raise ValueError('SCAN_SIGNAL_CHANGED')
                    ident=f"{SCOPE}|{symbol}|{signal['decision']}|{signal['closedCandleTimes']['5m']}"
                    tid='wxentry_'+hashlib.sha256(ident.encode()).hexdigest()[:24]
                    if any(r['id']==tid for r in engine.states()):continue
                    plan['authorization']={'host':HOST,'generation':sw['generation'],'configHash':digest}
                    item=engine.prepare(ident,plan);gateway.current=item['id'];gateway.ctx=ctx
                    engine.guard(item,ctx)
                    def refresh(s):
                        # The first snapshot is still fresh; subsequent calls after
                        # leverage setup collect all account and market evidence again.
                        if refresh.first:refresh.first=False;return ctx
                        _,fresh,_=capture_fn(reader,s,cfg);gateway.ctx=fresh;return fresh
                    refresh.first=True
                    result=engine.advance(item['id'],refresh)
                    if engine.writes(item['id']).get('ENTRY'):
                        result=reconcile(item['id']);attempts.append(result)
                        if result['state'] in ('PROTECTED','CLOSED'):opened.append(result)
                        if result['state'] not in ('PROTECTED','CLOSED','REJECTED'):
                            base['recoveryClear']=False;return report(root,'BLOCKED_AFTER_ENTRY',**base)
                    else:skipped.append({'symbol':symbol,'reason':result.get('state')})
                    rows=reader.account();cap=capacity(rows,root);base['capacity']=cap
                    if cap['count']>=cfg['telegramSettings']['maxConcurrentPositions']['default']:break
                except BudgetDeferred as exc:
                    skipped.append({'symbol':symbol,'reason':str(exc)})
                    break
                except Exception as exc:
                    skipped.append({'symbol':symbol,'reason':str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__})
                    # A write may have reached the exchange before any local error.
                    unresolved=[r for r in engine.states() if r['state'] not in ('CLOSED','REJECTED','SUPERSEDED','PROTECTED')
                        and engine.writes(r['id']).get('ENTRY')]
                    if unresolved:base['recoveryClear']=False;return report(root,'BLOCKED_AFTER_DISPATCH',**base)
            base['apiBudget']=budget().used()
            deferred=any(x.get('reason','').startswith('WAIT_API') for x in skipped)
            return report(root,'OPENED_PROTECTED' if opened else 'WAIT_API_BUDGET' if deferred else 'WAIT_SIGNAL_OR_GATES',**base)
        except BudgetDeferred as exc:
            try:
                from weex_trading_modes import cancel_pending_manual
                cancel_pending_manual(root,'WAIT_API_BUDGET')
            except Exception:pass
            return report(root,'WAIT_API_BUDGET',reason=str(exc),apiBudget=budget().used())
        except Exception as exc:
            try:
                from weex_trading_modes import cancel_pending_manual
                cancel_pending_manual(root,'WORKER_BLOCKED')
            except Exception:pass
            return report(root,'BLOCKED',reason=str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__)

if __name__=='__main__':
    import sys
    if len(sys.argv)==2 and sys.argv[1]=='--supervised-crash-child':
        # This separate certification entry point deliberately refuses to
        # transmit until a real independent supervisor supplies the exact
        # operation approval and independently measured recovery evidence.
        # The ordinary strategy release gate is NOT bypassed by this branch.
        from weex_supervised_entry_authority_bridge_v8 import run_connected
        try:
            run_connected(ROOT)
        except (PermissionError,ValueError) as exc:
            print('SUPERVISED_CRASH_CHILD_BLOCKED:'+str(exc))
            raise SystemExit(3)
        raise SystemExit(4)
    if len(sys.argv)==2 and sys.argv[1]=='--supervised-crash-recovery':
        # A fresh post-crash worker process: GET-only, no restart of entries.
        # The independent supervisor must have already observed a durable
        # UNKNOWN entry; it is never inferred from a flat account.
        from weex_supervised_crash_executor_v2 import CLIENT_ID
        from weex_supervised_real_recovery_v3 import read_exchange
        if control.state(ROOT)['mode']!='STOPPED' or control.build_errors(ROOT):
            raise SystemExit('RECOVERY_CONTROL_OR_BUILD_BLOCKED')
        try:
            proof=read_exchange(CLIENT_ID,root=ROOT)
        except Exception as exc:
            print(json.dumps({'status':'RECOVERY_READBACK_UNCERTAIN',
                              'errorType':type(exc).__name__,
                              'ordersSent':0,'entryRetries':0}))
            raise SystemExit(3)
        if proof.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE':
            print(json.dumps({'status':'RECOVERY_NOT_VERIFIED',
                              'ordersSent':0,'entryRetries':0}))
            raise SystemExit(3)
        print(json.dumps({'status':'WORKER_RESTART_PROTECTED_ENTRY_VERIFIED',
                          'clientOrderId':CLIENT_ID,
                          'entryOrderId':proof['entryOrderId'],
                          'stopAlgoId':proof['stopAlgoId'],
                          'positionId':proof['positionId'],
                          'ordersSent':0,'entryRetries':0}))
        raise SystemExit(0)
    if len(sys.argv)!=1:
        raise SystemExit('UNKNOWN_WORKER_ARGUMENT')
    r=run()
    if r['status'].startswith('BLOCKED'):raise SystemExit(2)
