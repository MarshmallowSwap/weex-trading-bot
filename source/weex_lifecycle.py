"""Persistent WEEX entry -> confirmed fills -> attributable TP -> confirmed close.

The runner uses PRETRADE mode and a GET-only SDK client. This same state machine
can use an explicitly scoped transport in a later authorized live test. It never
retries an uncertain write, modifies manual exposure, or uses close-all endpoints.
"""
import hashlib,json,sqlite3,time
from contextlib import closing
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

from weex_execution_readonly import pages
from weex_capacity import account_capacity


def dump(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def dec(x):
    v=Decimal(str(x))
    if not v.is_finite():raise ValueError('NONFINITE_NUMBER')
    return v
def now():return int(time.time()*1000)


class SDKGateway:
    def __init__(self,client):self.client=client
    def read(self,op,**query):
        from weex_simple_bot import read
        return read(self.client,op,**query)
    def write(self,op,payload):
        # HTTP authorization is separate from this engine's persistent dispatch checks.
        response=self.client.rest_api.execute_operation(op,payload)
        if response.status_code!=200:raise RuntimeError('EXCHANGE_WRITE_RESPONSE_UNKNOWN')
        return response.data


class Lifecycle:
    def __init__(self,path,gateway,config_reader):
        self.path=Path(path);self.gateway=gateway;self.config_reader=config_reader
        with closing(self.db()) as c,c:
            c.execute('''CREATE TABLE IF NOT EXISTS trades_v1 (
                id TEXT PRIMARY KEY,symbol TEXT NOT NULL,state TEXT NOT NULL,plan TEXT NOT NULL,
                owned TEXT,detail TEXT,created INTEGER NOT NULL,updated INTEGER NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS writes_v1 (
                trade_id TEXT NOT NULL,kind TEXT NOT NULL,operation TEXT NOT NULL,payload TEXT NOT NULL,
                state TEXT NOT NULL,response TEXT,at INTEGER NOT NULL,PRIMARY KEY(trade_id,kind))''')
            c.execute('''CREATE TABLE IF NOT EXISTS lifecycle_events_v1 (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,trade_id TEXT,state TEXT,detail TEXT,at INTEGER)''')
    def db(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row
        c.execute('PRAGMA synchronous=FULL');return c
    def event(self,c,tid,state,detail):
        c.execute('INSERT INTO lifecycle_events_v1(trade_id,state,detail,at) VALUES(?,?,?,?)',(tid,state,dump(detail),now()))
    def get(self,tid):
        with closing(self.db()) as c:r=c.execute('SELECT * FROM trades_v1 WHERE id=?',(tid,)).fetchone()
        if r is None:raise KeyError('UNKNOWN_TRADE')
        x=dict(r)
        for k in ('plan','owned','detail'):x[k]=json.loads(x[k]) if x[k] else None
        return x
    def states(self):
        with closing(self.db()) as c:return [dict(r) for r in c.execute('SELECT id,symbol,state FROM trades_v1')]
    def owned_position_ids(self):
        with closing(self.db()) as c:
            rows=c.execute("SELECT owned,plan FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')").fetchall()
        result=set()
        for r in rows:
            owned=json.loads(r['owned']) if r['owned'] else {}
            plan=json.loads(r['plan']) if r['plan'] else {}
            source=owned.get('entrySource',plan.get('entrySource','automatic')) if isinstance(owned,dict) else 'automatic'
            if source!='manual_telegram' and isinstance(owned,dict) and owned.get('positionId') is not None:
                result.add(str(owned['positionId']))
        return result
    def state(self,tid,state,detail=None,owned=None):
        with closing(self.db()) as c,c:
            c.execute('UPDATE trades_v1 SET state=?,detail=?,owned=COALESCE(?,owned),updated=? WHERE id=?',
                (state,dump(detail or {}),dump(owned) if owned is not None else None,now(),tid))
            self.event(c,tid,state,detail or {})
        return self.get(tid)
    def writes(self,tid):
        with closing(self.db()) as c:rows=c.execute('SELECT * FROM writes_v1 WHERE trade_id=?',(tid,)).fetchall()
        return {r['kind']:{**dict(r),'payload':json.loads(r['payload']),
                              'response':json.loads(r['response']) if r['response'] else None} for r in rows}
    def prepare(self,signal_id,plan):
        """Immutable actual entry payload. Dedicated TP gets its own attributable ID after fills."""
        p=json.loads(dump(plan));o=p['orderPreview'];symbol=o['symbol'];side=o['positionSide']
        from weex_trailing import is_trailing, number
        if is_trailing(p):
            policy=p['exitPolicy']
            if (not Decimal('.001')<=number(policy['callbackRate'])<=Decimal('.9999')
                    or number(policy['targetNetProfitUSDT'])!=number(p['targetNetProfitUSDT'])):
                raise ValueError('TRAILING_PLAN_INVALID')
        if dec(p['requestedLeverage'])<100:raise ValueError('LEVERAGE_BELOW_100')
        if side not in ('LONG','SHORT') or o['side']!=('BUY' if side=='LONG' else 'SELL'):
            raise ValueError('INVALID_SIDE')
        if o['type']!='MARKET' or dec(o['quantity'])<=0 or dec(p['targetNetProfitUSDT'])<=0:
            raise ValueError('INVALID_PLAN')
        if p.get('beforePositions') is None or any(x['symbol']==symbol for x in p['beforePositions']):
            raise ValueError('PREEXISTING_POSITION')
        digest=hashlib.sha256(signal_id.encode()).hexdigest()[:24]
        tid='wxentry_'+digest
        p['entry']={k:o[k] for k in ('symbol','side','positionSide','type','quantity')}
        if p.get('entrySource')=='supervised_crash_pilot':
            # Strictly scoped native attached stop for one-shot supervised
            # testing only. Ordinary strategy entries remain unchanged.
            price=dec(p.get('pilotReferencePrice',0))
            stop=dec(o.get('slTriggerPrice',0))
            qty=dec(o['quantity'])
            if (symbol!='ETHUSDT' or side!='LONG' or o['side']!='BUY'
                    or dec(p['requestedLeverage'])!=100 or qty!=Decimal('0.001')
                    or price<=0 or price*qty>Decimal('5')
                    or o.get('SlWorkingType')!='MARK_PRICE'
                    or not Decimal('0')<(price-stop)/price<=Decimal('0.005')):
                raise ValueError('SUPERVISED_ATOMIC_STOP_SCOPE_INVALID')
            p['entry']['slTriggerPrice']=str(stop)
            p['entry']['SlWorkingType']='MARK_PRICE'
        p['entry']['newClientOrderId']=tid
        p['tpClientId']='wxtp_'+digest
        p['setupRequests']=[{'operation':'post_capi_v3_account_marginType','payload':{'symbol':symbol,'marginType':'CROSSED'}},
            {'operation':'post_capi_v3_account_leverage','payload':{'symbol':symbol,'marginType':'CROSSED','crossLeverage':str(p['requestedLeverage'])}}]
        with closing(self.db()) as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT plan FROM trades_v1 WHERE id=?',(tid,)).fetchone()
            if old:
                if old['plan']!=dump(p):raise ValueError('IMMUTABLE_LIFECYCLE_PLAN_CONFLICT')
                c.rollback();return self.get(tid)
            active=c.execute("SELECT id,state FROM trades_v1 WHERE symbol=? AND state NOT IN ('CLOSED','REJECTED','SUPERSEDED')",(symbol,)).fetchall()
            for r in active:
                if r['state']!='PREPARED' or c.execute('SELECT 1 FROM writes_v1 WHERE trade_id=?',(r['id'],)).fetchone():
                    raise ValueError('UNRESOLVED_SYMBOL_LIFECYCLE')
                c.execute("UPDATE trades_v1 SET state='SUPERSEDED' WHERE id=?",(r['id'],))
                self.event(c,r['id'],'SUPERSEDED',{'by':tid})
            c.execute('INSERT INTO trades_v1 VALUES(?,?,?,?,NULL,NULL,?,?)',(tid,symbol,'PREPARED',dump(p),now(),now()))
            self.event(c,tid,'PREPARED',{'ordersSubmitted':False});c.commit()
        return self.get(tid)
    def send_once(self,tid,kind,operation,payload,*,capacity=None):
        cfg=self.config_reader()
        if cfg.get('execution',{}).get('enabled') is not True or cfg['execution'].get('mode')!='LIVE':
            return {'state':'STOP_BEFORE_SUBMISSION','sent':False}
        with closing(self.db()) as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM writes_v1 WHERE trade_id=? AND kind=?',(tid,kind)).fetchone():
                c.rollback();return {'state':'RECONCILE_NO_RETRY','sent':False}
            if kind=='ENTRY':
                plan=json.loads(c.execute('SELECT plan FROM trades_v1 WHERE id=?',(tid,)).fetchone()['plan'])
                if dec(plan['requestedLeverage'])<max(Decimal(100),dec(cfg['risk'].get('minimumLeverage',100))):
                    c.rollback();return {'state':'LEVERAGE_BELOW_MINIMUM','sent':False}
                if capacity is None:raise ValueError('MISSING_CAPACITY_SNAPSHOT')
                if plan.get('entrySource')!='manual_telegram':
                    cap=cfg['telegramSettings']['maxConcurrentPositions']['default']
                    active=c.execute("SELECT t.symbol FROM trades_v1 t JOIN writes_v1 w ON t.id=w.trade_id WHERE w.kind='ENTRY' AND t.id<>? AND t.state NOT IN ('CLOSED','REJECTED','SUPERSEDED')",(tid,)).fetchall()
                    unresolved={r['symbol'] for r in active}-set(capacity['symbols'])
                    if capacity['count']+len(unresolved)>=cap:
                        c.rollback();return {'state':'CAPACITY_RESERVED_BY_OTHER_ENTRY','sent':False}
                if cfg.get('risk',{}).get('stopLoss',{}).get('enabled') is not False or cfg['execution'].get('allowOrdersWithoutStop') is not True:
                    c.rollback();return {'state':'STOP_POLICY_CHANGED','sent':False}
            if kind=='TP_REPAIR':
                from weex_tp_local_notsent_repair import eligible
                item=self.get(tid)
                prior=self.writes(tid)
                if not eligible(prior,item.get('owned')):
                    raise PermissionError('TP_REPAIR_REQUIRES_PROVEN_LOCAL_NON_SUBMISSION')
                if operation!=prior['TP']['operation'] or payload!=prior['TP']['payload']:
                    raise PermissionError('TP_REPAIR_MUST_MATCH_ORIGINAL_REQUEST')
            c.execute('INSERT INTO writes_v1 VALUES(?,?,?,?,?,NULL,?)',(tid,kind,operation,dump(payload),'UNKNOWN',now()))
            self.event(c,tid,kind+'_UNKNOWN',{'committedBeforeDispatch':True});c.commit()
        try:
            response=self.gateway.write(operation,payload)
            # Injection seam for an explicitly supplied TEST gateway only.
            # Production SDKGateway/Gateway do not expose this callable.
            # A child process may die here after exchange ACK, before SQLite
            # acknowledgement; durable UNKNOWN must never cause a resend.
            crash_probe=getattr(self.gateway,'_test_crash_after_entry_ack',None)
            if kind=='ENTRY' and callable(crash_probe):
                crash_probe(tid,operation,payload,response)
        except Exception as exc:
            return {'state':'UNKNOWN','sent':None,'error':type(exc).__name__}
        with closing(self.db()) as c,c:
            c.execute("UPDATE writes_v1 SET state='RESPONSE_RECEIVED',response=? WHERE trade_id=? AND kind=?",(dump(response),tid,kind))
            self.event(c,tid,kind+'_RESPONSE',{'responsePersisted':True})
        return {'state':'RESPONSE_RECEIVED','response':response,'sent':True}
    def guard(self,item,context):
        p=item['plan'];symbol=item['symbol'];cfg=self.config_reader()
        if dec(p['requestedLeverage'])<max(Decimal(100),dec(cfg['risk'].get('minimumLeverage',100))):
            raise ValueError('LEVERAGE_BELOW_MINIMUM')
        if dec(context['maximumPermittedLeverage'])!=dec(p['requestedLeverage']):
            raise ValueError('MAXIMUM_LEVERAGE_CHANGED_REPLAN_REQUIRED')
        if not 0<=now()-int(context['observedAtMs'])<=5000:raise ValueError('STALE_PREFLIGHT')
        if context.get('complete') is not True or context.get('apiEnabled') is not True:raise ValueError('INCOMPLETE_PREFLIGHT')
        if context.get('accountCanTrade') is not True or context.get('hedgeMode') is not True:raise ValueError('ACCOUNT_MODE')
        if p.get('entrySource')=='manual_telegram':
            if context.get('marketDataValid') is not True:raise ValueError('LIVE_ORDERBOOK_UNAVAILABLE')
        elif context.get('depthUnitVerified') is not True or context.get('liquidityPassed') is not True:
            raise ValueError('LIQUIDITY_UNVERIFIED')
        if context.get('marketSignal')!=p['entry']['positionSide']:raise ValueError('SIGNAL_CHANGED')
        if p.get('closedCandleTimes') and p['closedCandleTimes']!=context.get('closedCandleTimes'):
            raise ValueError('SIGNAL_CANDLE_CHANGED_REPLAN_REQUIRED')
        if context.get('riskTierVerified') is not True:raise ValueError('LEVERAGE_TIER_UNVERIFIED')
        if dec(context['exitFeeRate'])!=dec(p['exitFeeRate']):raise ValueError('FEES_CHANGED_REPLAN_REQUIRED')
        if dec(cfg['strategySettings']['targetNetProfitUSDT'])!=dec(p['targetNetProfitUSDT']):raise ValueError('TP_SETTING_CHANGED')
        if cfg['strategySettings'].get('tpAccountingMode','NET')!=p.get('tpAccountingMode','NET'):
            raise ValueError('TP_ACCOUNTING_MODE_CHANGED')
        from weex_trailing import is_trailing
        if is_trailing(p)!=(cfg['strategySettings'].get('tpMode','fixed')=='trailing'):
            raise ValueError('TP_MODE_CHANGED_REPLAN_REQUIRED')
        if dec(context['availableBalance'])<dec(p['requiredMarginAndEntryFeeUSDT']):raise ValueError('BALANCE')
        rows=context['positions']+context['openOrders']+context['conditionalOrders']
        if any(r['symbol']==symbol for r in rows):raise ValueError('SYMBOL_OCCUPIED')
        if p.get('entrySource')!='manual_telegram':
            cap=cfg['telegramSettings']['maxConcurrentPositions']['default']
            capacity=account_capacity(context['positions'],context['openOrders']+context['conditionalOrders'],
                                      managed_position_ids=self.owned_position_ids())
            if type(cap) is not int or not 1<=cap<=10 or capacity['count']>=cap:raise ValueError('POSITION_LIMIT')
            occupied=set(capacity['symbols'])
            unresolved={r['symbol'] for r in self.states() if r['id']!=item['id']
                        and r['state'] not in ('PREPARED','SUPERSEDED','CLOSED','REJECTED')}
            if capacity['count']+len(unresolved-occupied)>=cap:raise ValueError('UNRESOLVED_ENTRY_CAPACITY')
        if cfg['risk']['stopLoss']['enabled'] is not False or cfg['execution'].get('allowOrdersWithoutStop') is not True:
            raise ValueError('STOP_POLICY_NOT_SUPPORTED_OR_AUTHORIZED')
        # A preview may be old even if account observations are fresh. Validate current market price.
        current=dec(context['referencePrice']);planned=dec(p['sizing']['notionalUSDT'])/dec(p['entry']['quantity'])
        if current<=0 or abs(current/planned-1)>Decimal('0.001'):raise ValueError('PRICE_MOVED_REPLAN_REQUIRED')
        cost_mode = cfg['risk'].get('entryBudgetMode') == 'COST_INCLUDING_ENTRY_FEE'
        plan_cost_mode = p['sizing'].get('budgetMode') == 'COST_INCLUDING_ENTRY_FEE'
        if cost_mode != plan_cost_mode:
            raise ValueError('BUDGET_MODE_CHANGED_REPLAN_REQUIRED')
        if cost_mode:
            budget=dec(cfg['risk']['orderCostTargetUSDT'])
            if budget <= 0 or budget != dec(p['sizing']['targetCostUSDT']):
                raise ValueError('COST_SETTING_CHANGED_REPLAN_REQUIRED')
            entry_fee=dec(p['sizing']['entryFeeRate'])
            if not 0<=entry_fee<1 or entry_fee!=dec(context['exitFeeRate']):
                raise ValueError('ENTRY_FEE_CHANGED_REPLAN_REQUIRED')
            required=dec(p['entry']['quantity'])*current*(1/dec(p['requestedLeverage'])+entry_fee)
            if required>budget:raise ValueError('COST_LIMIT_AFTER_PRICE_MOVE')
            if required>dec(context['availableBalance']):raise ValueError('BALANCE_AFTER_PRICE_MOVE')
        elif dec(p['entry']['quantity'])*current/dec(p['requestedLeverage'])>dec(cfg['risk']['initialMarginTargetUSDT']):
            raise ValueError('MARGIN_LIMIT_AFTER_PRICE_MOVE')
        return True
    def advance(self,tid,context_provider):
        item=self.get(tid);cfg=self.config_reader()
        if item['state'] in ('CLOSED','REJECTED','SUPERSEDED'):return item
        if cfg.get('execution',{}).get('enabled') is not True or cfg['execution'].get('mode')!='LIVE':
            return {'state':'STOP_BEFORE_SUBMISSION','tradeId':tid,'entry':item['plan']['entry'],
                    'setupRequests':item['plan']['setupRequests'],'ordersSubmitted':False}
        if self.writes(tid).get('ENTRY'):return self.reconcile(tid)
        try:
            context=context_provider(item['symbol']);self.guard(item,context)
        except (KeyError,ValueError,TypeError,ArithmeticError) as exc:
            return {'state':'PREFLIGHT_BLOCKED','reason':str(exc),'ordersSubmitted':False}
        expected=dec(item['plan']['requestedLeverage'])
        for kind,index in (('MARGIN',0),('LEVERAGE',1)):
            conf=context['symbolConfig']
            satisfied=conf.get('marginType')=='CROSSED' if kind=='MARGIN' else conf.get('marginType')=='CROSSED' and dec(conf['crossLeverage'])==expected
            if not satisfied:
                request=item['plan']['setupRequests'][index]
                self.send_once(tid,kind,request['operation'],request['payload'])
                try:
                    context=context_provider(item['symbol']);self.guard(item,context)
                except Exception as exc:
                    return {'state':'ACCOUNT_SETUP_UNCONFIRMED','reason':type(exc).__name__,'ordersSubmitted':False}
                conf=context['symbolConfig']
                satisfied=conf.get('marginType')=='CROSSED' if kind=='MARGIN' else conf.get('marginType')=='CROSSED' and dec(conf['crossLeverage'])==expected
                if not satisfied:return {'state':'ACCOUNT_SETUP_UNCONFIRMED','ordersSubmitted':False}
        self.state(tid,'ENTRY_PENDING')
        capacity=account_capacity(context['positions'],context['openOrders']+context['conditionalOrders'],
                                  managed_position_ids=self.owned_position_ids())
        result=self.send_once(tid,'ENTRY','post_capi_v3_order',item['plan']['entry'],capacity=capacity)
        if result.get('sent') is False and result['state']!='RECONCILE_NO_RETRY':return result
        return self.reconcile(tid)
    def observations(self,item):
        """Bounded snapshots. History absence or truncation never allows a resend."""
        start=now();r=self.gateway.read;s=item['symbol'];w=self.writes(item['id'])
        entry_response=(w.get('ENTRY') or {}).get('response') or {}
        opened=pages(r,'get_capi_v3_openOrders',identity='orderId',start=0,symbol=s)
        from weex_trailing import is_trailing, TYPES
        if is_trailing(item['plan']):
            opened=[o for o in opened if not (o.get('clientOrderId')==item['plan']['tpClientId'] and o.get('type') in TYPES)]
        if isinstance(entry_response,dict) and entry_response.get('success') is True and entry_response.get('orderId'):
            history=[r('get_capi_v3_order',orderId=entry_response['orderId'])]
        else:
            history=pages(r,'get_capi_v3_order_history',identity='orderId',start=0,symbol=s,
                          startTime=item['created']-1000,endTime=now())
        matches={}
        for o in history+opened:
            if o.get('clientOrderId')==item['id']:
                key=str(o['orderId'])
                if key in matches and any(o.get(k)!=matches[key].get(k) for k in ('status','executedQty','side','positionSide','symbol')):
                    raise ValueError('CHANGING_ORDER_SNAPSHOT')
                matches[key]=o
        if len(matches)!=1:raise ValueError('ENTRY_NOT_UNIQUELY_OBSERVED')
        order=next(iter(matches.values()))
        if isinstance(entry_response,dict) and entry_response.get('orderId') and str(entry_response['orderId'])!=str(order['orderId']):
            raise ValueError('ENTRY_ACK_CONTRADICTS_OBSERVATION')
        p=item['plan'];entry=p['entry']
        if any(order.get(k)!=entry[k] for k in ('symbol','side','positionSide')):raise ValueError('ENTRY_BINDING')
        if any(o.get('clientOrderId')!=item['id'] for o in opened):raise ValueError('OTHER_SYMBOL_ORDER')
        trades=r('get_capi_v3_userTrades',symbol=s,orderId=order['orderId'],limit=100)
        if not isinstance(trades,list) or len(trades)>=100:raise ValueError('INCOMPLETE_FILLS')
        positions=r('get_capi_v3_account_position_allPosition')
        if not isinstance(positions,list) or any(not isinstance(x,dict) or not x.get('symbol') for x in positions):raise ValueError('INVALID_POSITIONS')
        algos=pages(r,'get_capi_v3_openAlgoOrders',identity='algoId',start=1,symbol=s)
        prior=r('get_capi_v3_allAlgoOrders',symbol=s,startTime=item['created']-1000,endTime=now(),limit=1000)
        if not isinstance(prior,dict) or prior.get('hasMore') is not False or not isinstance(prior.get('orders'),list):raise ValueError('INCOMPLETE_ALGO_HISTORY')
        if is_trailing(item['plan']):
            from weex_trailing import OPEN_OPERATION,HISTORY_OPERATION,merge
            trailing_open=pages(r,OPEN_OPERATION,identity='orderId',start=0,symbol=s)
            trailing_history=pages(r,HISTORY_OPERATION,identity='orderId',start=0,symbol=s,
                                  startTime=item['created']-1000,endTime=now())
            algos=merge(algos,trailing_open)
            prior={**prior,'orders':merge(prior['orders'],trailing_history)}
        known={}
        for a in prior['orders']+algos:
            key=str(a['algoId'])
            if key in known and any(a.get(k)!=known[key].get(k) for k in
                    ('clientAlgoId','symbol','positionSide','side','orderType','algoStatus','actualOrderId',
                     'quantity','triggerPrice','workingType','reduceOnly','closePosition','activatePrice','callbackRate')):
                raise ValueError('CHANGING_TP_SNAPSHOT')
            known[key]=a
        if now()-start>5000:raise ValueError('SNAPSHOT_TOO_SLOW')
        return order,trades,positions,list(known.values()),algos
    def fills(self,order,trades):
        qty=Decimal(0);cost=Decimal(0);fees=Decimal(0);seen=set()
        for t in trades:
            if (str(t.get('orderId'))!=str(order['orderId']) or any(t.get(k)!=order[k] for k in ('symbol','side','positionSide'))
                    or not t.get('id') or str(t['id']) in seen):raise ValueError('FILL_BINDING')
            q=dec(t['qty']);price=dec(t['price']);fee=dec(t['commission'])
            if q<=0 or price<=0 or fee<0 or t['commissionAsset']!='USDT':raise ValueError('FILL_UNITS_OR_FEE')
            seen.add(str(t['id']));qty+=q;cost+=q*price;fees+=fee
        if qty!=dec(order['executedQty']):raise ValueError('FILL_TOTAL_MISMATCH')
        return qty,cost,fees
    def entry_fills(self,item,order,trades,positions):
        return self.fills(order,trades),None
    def reconcile(self,tid):
        started=now()
        item=self.get(tid);w=self.writes(tid)
        if item['state'] in ('CLOSED','REJECTED','SUPERSEDED'):return item
        if 'ENTRY' not in w:return {'state':'NEVER_SUBMITTED','ordersSubmitted':False}
        ack=w['ENTRY']['response']
        if isinstance(ack,dict) and ack.get('success') is False:return self.state(tid,'REJECTED',{'source':'EXCHANGE_ACK'})
        try:
            order,trades,positions,algos,opened_algos=self.observations(item)
            (qty,cost,fees),entry_evidence=self.entry_fills(item,order,trades,positions);p=item['plan'];requested=dec(p['entry']['quantity'])
            if qty>requested:raise ValueError('EXCESS_FILL')
            own=[x for x in positions if x['symbol']==item['symbol']]
            terminal=order.get('status') in ('FILLED','CANCELED','EXPIRED','REJECTED')
            if not terminal:
                if qty>0:
                    self.send_once(tid,'CANCEL_REMAINDER','delete_capi_v3_order',{'query':{'orderId':order['orderId']}})
                return self.state(tid,'ENTRY_PENDING',{'filledQty':str(qty),'awaitTerminalOrder':True})
            if qty==0:return self.state(tid,'REJECTED',{'source':'TERMINAL_ZERO_FILL'})
            if qty<requested and order['status']=='FILLED':raise ValueError('INCONSISTENT_FILLED_STATUS')
            owned=item['owned']
            if owned and (str(order['orderId'])!=owned['entryOrderId'] or qty!=dec(owned['quantity'])
                    or cost!=dec(owned['actualEntryCostUSDT']) or fees!=dec(owned['actualEntryFeesUSDT'])):
                raise ValueError('ENTRY_ECONOMICS_CHANGED_AFTER_TP_PLAN')
            if not owned:
                if len(own)!=1 or own[0].get('side')!=p['entry']['positionSide'] or dec(own[0]['size'])!=qty or not own[0].get('id'):
                    raise ValueError('POSITION_NOT_ATTRIBUTABLE')
                # WEEX UI "PnL" is a calculator, not an API order parameter.
                # Explicitly convert net USDT to the server's required triggerPrice.
                from weex_tp_pnl_preview import preview as pnl_preview, gross_preview
                mode=p.get('tpAccountingMode','NET')
                if mode=='GROSS_BEFORE_COSTS':
                    pnl=gross_preview(side=p['entry']['positionSide'],quantity=qty,
                        entry_cost_usdt=cost,entry_fees_usdt=fees,
                        exit_fee_rate=p['exitFeeRate'],
                        target_gross_usdt=p['targetNetProfitUSDT'],
                        price_tick=p['sizing']['priceTick'])
                elif mode=='NET':
                    pnl=pnl_preview(side=p['entry']['positionSide'],quantity=qty,
                        entry_cost_usdt=cost,entry_fees_usdt=fees,
                        exit_fee_rate=p['exitFeeRate'],
                        target_net_usdt=p['targetNetProfitUSDT'],
                        price_tick=p['sizing']['priceTick'])
                else:
                    raise ValueError('INVALID_TP_ACCOUNTING_MODE')
                trigger=dec(pnl['triggerPrice'])
                tick=dec(p['sizing']['priceTick'])
                tp={'symbol':item['symbol'],'clientAlgoId':p['tpClientId'],'planType':'TAKE_PROFIT',
                    'triggerPrice':format(trigger,'f'),'executePrice':'0','quantity':format(qty,'f'),
                    'positionSide':p['entry']['positionSide'],'triggerPriceType':'MARK_PRICE','reduceOnly':True,'closePosition':False}
                from weex_trailing import is_trailing, request_from_fixed_tp
                fixed_trigger=tp['triggerPrice']
                if is_trailing(p):tp=request_from_fixed_tp(tp,p['exitPolicy'],tick)
                owned={'positionId':str(own[0]['id']),'quantity':str(qty),'entryOrderId':str(order['orderId']),
                       'actualEntryCostUSDT':str(cost),'actualEntryFeesUSDT':str(fees),'tpRequest':tp,
                       'tpPnlPreview':pnl}
                if is_trailing(p):
                    owned['tpOperation']='post_capi_v3_algoOrder'
                    owned['fixedNetTargetPrice']=fixed_trigger
                owned['entrySource']=p.get('entrySource','automatic')
                if entry_evidence is not None:owned['entryFillEvidence']=entry_evidence
                item=self.state(tid,'ENTRY_FILLED',{'partialEntry':qty<requested},owned=owned)
            from weex_trailing import is_trailing
            tp=owned['tpRequest']
            matches=[a for a in algos if a.get('clientAlgoId')==p['tpClientId']]
            if len(matches)>1:raise ValueError('AMBIGUOUS_TP')
            if not matches:
                if any(a.get('clientAlgoId')!=p['tpClientId'] for a in opened_algos):raise ValueError('EXISTING_OTHER_PROTECTION')
                if (len(own)!=1 or str(own[0].get('id'))!=owned['positionId']
                        or own[0].get('side')!=tp['positionSide'] or dec(own[0]['size'])!=qty):raise ValueError('EXPOSURE_CHANGED_BEFORE_TP')
                # Phase-2 gate: never place a TP on a changed position, nor
                # let a stale/corrupt trigger differ from the fill-based PnL calculation.
                if ('openValue' in own[0] and dec(own[0]['openValue'])!=cost
                        or 'openFee' in own[0] and dec(own[0]['openFee'])!=fees):
                    raise ValueError('POSITION_ECONOMICS_CHANGED_BEFORE_TP')
                if not is_trailing(p):
                    check=owned.get('tpPnlPreview')
                    accounting=p.get('tpAccountingMode','NET')
                    if not isinstance(check,dict) or dec(check['triggerPrice'])!=dec(tp['triggerPrice']):
                        raise ValueError('PNL_TP_VALIDATION_FAILED')
                    if accounting=='GROSS_BEFORE_COSTS':
                        if (check.get('mode')!='PNL_GROSS_BEFORE_COSTS_USDT'
                                or dec(check['estimatedGrossAtTriggerUSDT'])<dec(p['targetNetProfitUSDT'])):
                            raise ValueError('GROSS_TP_VALIDATION_FAILED')
                    elif accounting=='NET':
                        if (check.get('mode')!='PNL_NET_USDT'
                                or dec(check['estimatedNetAtTriggerUSDT'])<dec(p['targetNetProfitUSDT'])):
                            raise ValueError('PNL_TP_VALIDATION_FAILED')
                    else:
                        raise ValueError('TP_ACCOUNTING_MODE_INVALID')
                from weex_tp_local_notsent_repair import eligible as repair_eligible,marker as notsent
                prior=self.writes(tid)
                if 'TP' in prior:
                    if repair_eligible(prior,owned):
                        result=self.send_once(tid,'TP_REPAIR',owned.get('tpOperation','post_capi_v3_placeTpSlOrder'),tp)
                        response=self.writes(tid).get('TP_REPAIR',{}).get('response')
                        if notsent(response):
                            return self.state(tid,'REVIEW_REQUIRED',{'reason':'TP_REPAIR_NOT_SENT_ONE_ATTEMPT_EXHAUSTED'})
                        return self.state(tid,'TP_PENDING',{'dispatch':result['state'],'confirmed':False,'repairAttempted':True})
                    if 'TP_REPAIR' in prior:
                        if notsent(prior['TP_REPAIR'].get('response')):
                            return self.state(tid,'REVIEW_REQUIRED',{'reason':'TP_REPAIR_NOT_SENT_ONE_ATTEMPT_EXHAUSTED'})
                        return self.state(tid,'TP_PENDING',{'reason':'AWAIT_TP_REPAIR_EXCHANGE_READBACK','repairAttempted':True})
                    if notsent(prior['TP'].get('response')):
                        return self.state(tid,'REVIEW_REQUIRED',{'reason':'TP_LOCAL_NON_SUBMISSION_UNSAFE_TO_REPAIR'})
                    response=prior['TP'].get('response')
                    if isinstance(response,list):response=response[0] if len(response)==1 else None
                    if isinstance(response,dict) and response.get('success') is False:
                        return self.state(tid,'REVIEW_REQUIRED',{'reason':'TP_EXCHANGE_REJECTED_NO_AUTOMATIC_RETRY'})
                    return self.state(tid,'TP_PENDING',{'reason':'AWAIT_ORIGINAL_TP_EXCHANGE_READBACK'})
                result=self.send_once(tid,'TP',owned.get('tpOperation','post_capi_v3_placeTpSlOrder'),tp)
                response=self.writes(tid).get('TP',{}).get('response')
                if isinstance(response,dict):response=[response]
                if isinstance(response,list) and len(response)==1 and response[0].get('success') is False:
                    if notsent(response):
                        return self.state(tid,'TP_PENDING',{'reason':'LOCALLY_NOT_SENT_VERIFIED_RECHECK_REQUIRED'})
                    return self.state(tid,'REVIEW_REQUIRED',{'reason':'TP_REJECTED_POSITION_UNPROTECTED'})
                return self.state(tid,'TP_PENDING',{'dispatch':result['state'],'confirmed':False})
            a=matches[0]
            from weex_trailing import is_trailing,matches_request
            trailing_exit=is_trailing(p)
            if trailing_exit:
                if not matches_request(a,tp):raise ValueError('TP_PARAMETERS_CHANGED')
            elif (a.get('symbol')!=item['symbol'] or a.get('positionSide')!=tp['positionSide']
                    or a.get('side')!=('SELL' if tp['positionSide']=='LONG' else 'BUY')
                    or a.get('orderType')!='TAKE_PROFIT_MARKET' or a.get('reduceOnly') is not True
                    or dec(a['quantity'])!=qty or dec(a['triggerPrice'])!=dec(tp['triggerPrice'])
                    or a.get('workingType')!='MARK_PRICE'):raise ValueError('TP_PARAMETERS_CHANGED')
            if 'TP' not in w:raise ValueError('TP_WITHOUT_OUR_DISPATCH')
            from weex_tp_local_notsent_repair import marker as local_notsent
            if local_notsent(w['TP'].get('response')) and 'TP_REPAIR' not in w:
                raise ValueError('TP_OBSERVED_AFTER_VERIFIED_NON_SEND_WITHOUT_REPAIR')
            response=(w['TP_REPAIR'] if 'TP_REPAIR' in w and local_notsent(w['TP'].get('response'))
                      else w['TP']).get('response')
            if isinstance(response,dict):response=[response]
            if isinstance(response,list) and len(response)==1:
                if response[0].get('success') is False or (response[0].get('orderId') and str(response[0]['orderId'])!=str(a['algoId'])):
                    raise ValueError('TP_ACK_CONTRADICTS_HISTORY')
            if a.get('algoStatus') in ('NEW','UNTRIGGERED'):
                if (len(own)!=1 or str(own[0]['id'])!=owned['positionId']
                        or own[0].get('side')!=tp['positionSide'] or dec(own[0]['size'])!=qty):raise ValueError('PROTECTED_EXPOSURE_CHANGED')
                return self.state(tid,'PROTECTED',{'tpId':str(a['algoId']),'quantity':str(qty)})
            if a.get('algoStatus') in ('FILLED','TRIGGERED'):
                if own:raise ValueError('EXIT_PARTIAL_OR_POSITION_CHANGED')
                exit_id=a.get('actualOrderId') or a['algoId']
                close=self.gateway.read('get_capi_v3_order',orderId=exit_id)
                # Observed WEEX demo format: a filled TP may itself be the order,
                # with actualOrderId=null. Require exact client ID and TP type;
                # absence or ambiguity never permits a guessed closure or resend.
                if not a.get('actualOrderId') and (
                        close.get('clientOrderId')!=tp['clientAlgoId']
                        or close.get('type') not in (('TRAILING_MARKET','TRAILING_STOP_MARKET') if trailing_exit else ('TAKE_PROFIT_MARKET',))):
                    raise ValueError('EXIT_ALGO_ORDER_BINDING')
                if (str(close.get('orderId'))!=str(exit_id) or close.get('symbol')!=item['symbol']
                        or close.get('positionSide')!=tp['positionSide'] or close.get('side')!=a['side']
                        or close.get('reduceOnly') is not True or close.get('status')!='FILLED'):raise ValueError('EXIT_ORDER_BINDING')
                fills=self.gateway.read('get_capi_v3_userTrades',symbol=item['symbol'],orderId=close['orderId'],limit=100)
                if not isinstance(fills,list) or len(fills)>=100:raise ValueError('EXIT_FILLS_INCOMPLETE')
                closed,exit_value,exit_fees=self.fills(close,fills)
                if closed!=qty:raise ValueError('EXIT_QUANTITY_MISMATCH')
                latest=self.gateway.read('get_capi_v3_account_position_allPosition')
                if (not isinstance(latest,list) or any(not isinstance(x,dict) or not x.get('symbol') or x['symbol']==item['symbol'] for x in latest)
                        or now()-started>5000):raise ValueError('CLOSE_SNAPSHOT_CHANGED_OR_STALE')
                gross=exit_value-cost if p['entry']['side']=='BUY' else cost-exit_value
                net=gross-fees-exit_fees
                return self.state(tid,'CLOSED',{'tpId':str(a['algoId']),'exitOrderId':str(close['orderId']),'quantity':str(qty),
                    'actualExitValueUSDT':str(exit_value),'actualExitFeesUSDT':str(exit_fees),
                    'realizedNetBeforeFundingUSDT':str(net),'realizedGrossBeforeCostsUSDT':str(gross),
                    'tpAccountingMode':p.get('tpAccountingMode','NET'),'fundingIncluded':False,
                    'targetMetBeforeFunding':(gross if p.get('tpAccountingMode','NET')=='GROSS_BEFORE_COSTS'
                                              else net)>=dec(p['targetNetProfitUSDT'])})
            return self.state(tid,'REVIEW_REQUIRED',{'reason':'TP_NOT_ACTIVE','algoStatus':a.get('algoStatus')})
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            return self.state(tid,'REVIEW_REQUIRED',{'reason':str(exc)})
        except Exception as exc:
            return self.state(tid,'RECONCILIATION_PENDING',{'error':type(exc).__name__})
