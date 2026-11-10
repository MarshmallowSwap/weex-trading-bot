import copy,json,tempfile,unittest
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from unittest.mock import patch
from weex_trailing import (entry_policy,request_from_fixed_tp,normalize,merge,matches_request,
                          OPERATION,OPEN_OPERATION,HISTORY_OPERATION)
from weex_lifecycle import Lifecycle,now
from weex_http_guard import prepare_sdk_request
from weex_capacity import account_capacity,full_closing_tp
from test_weex_lifecycle import Exchange,PLAN,CFG

def signal(atr='0.3'):
    return {'observedAt':datetime.now(timezone.utc).isoformat(),
            'closedCandleTimes':{'5m':now()-1000},'timeframes':{'5m':{'atrPct':atr}}}

class TrailingExchange(Exchange):
    def __init__(self):
        super().__init__();self.trailing=[];self.history=[];self.exit=None;self.exit_fills=[]
        self.extreme=None;self.active=False
    def write(self,op,p):
        if op!=OPERATION:
            result=super().write(op,p)
            if op=='post_capi_v3_order':
                self.order['cumQuote']=str(D(self.order['executedQty'])*2500)
                for fill in self.trades:fill['quoteQty']=str(D(fill['qty'])*D(fill['price']))
            return result
        self.calls.append((op,copy.deepcopy(p)))
        if self.fail=='reject_trailing':return {'success':False,'errorCode':'TEST_REJECT'}
        self.trailing=[{**p,'orderId':'2','clientOrderId':p['clientAlgoId'],'origQty':p['quantity'],
                        'status':'UNACTIVATED','executedQty':'0'}]
        if self.fail=='trailing':raise TimeoutError('simulated lost acknowledgement')
        return {'success':True,'orderId':'2','clientOrderId':p['clientAlgoId']}
    def read(self,op,**q):
        if op==OPEN_OPERATION:return copy.deepcopy(self.trailing)
        if op==HISTORY_OPERATION:return copy.deepcopy(self.history)
        if op=='get_capi_v3_order' and str(q.get('orderId'))=='2':return copy.deepcopy(self.exit)
        if op=='get_capi_v3_userTrades' and str(q.get('orderId'))=='2':return copy.deepcopy(self.exit_fills)
        return super().read(op,**q)
    def price(self,value):
        """Exchange-side trailing simulation; bot does not receive price ticks."""
        if not self.trailing:return
        p=self.trailing[0];price=D(value);long=p['positionSide']=='LONG';activation=D(p['activatePrice'])
        if not self.active:
            if (price<activation if long else price>activation):return
            self.active=True;p['status']='ACTIVE';self.extreme=price
        self.extreme=max(self.extreme,price) if long else min(self.extreme,price)
        trigger=self.extreme*(1-D(p['callbackRate']) if long else 1+D(p['callbackRate']))
        if (price>trigger if long else price<trigger):return
        p['status']='FILLED';p['executedQty']=p['quantity'];self.history=[copy.deepcopy(p)]
        self.exit=copy.deepcopy(p)
        self.exit['cumQuote']=str(D(p['quantity'])*price)
        self.exit_fills=[{'id':'exit-fill','orderId':'2','symbol':p['symbol'],'side':p['side'],
            'positionSide':p['positionSide'],'qty':p['quantity'],'price':str(price),
            'commission':'0.04','commissionAsset':'USDT','quoteQty':str(D(p['quantity'])*price)}]
        self.trailing=[];self.positions=[]

class NativeTrailingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.sqlite3'
        self.cfg=copy.deepcopy(CFG);self.cfg['strategySettings']['tpMode']='trailing'
        self.exchange=TrailingExchange();self.engine=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.plan=copy.deepcopy(PLAN);self.plan['exitPolicy']=entry_policy(signal(),self.plan['targetNetProfitUSDT'])
        self.item=self.engine.prepare('native-trailing',self.plan);self.tid=self.item['id']
    def start(self):
        # Entry itself is exercised by advance with the same account guards as fixed TP.
        ctx={'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,
         'hedgeMode':True,'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':self.plan['orderPreview']['positionSide'],
         'riskTierVerified':True,'availableBalance':'100','positions':[],'openOrders':[],
         'conditionalOrders':[],'symbolConfig':{'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'100'},
         'referencePrice':'2500','exitFeeRate':'0.0008','maximumPermittedLeverage':'100'}
        return self.engine.advance(self.tid,lambda _:ctx)
    def test_full_long_activation_follow_pullback_and_restart(self):
        self.assertEqual(self.start()['state'],'TP_PENDING')
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'PROTECTED')
        owned=self.engine.get(self.tid)['owned'];request=owned['tpRequest'];activation=D(request['activatePrice'])
        self.assertEqual(activation,D(owned['fixedNetTargetPrice']))
        self.exchange.price(str(activation-D('.01')));self.assertFalse(self.exchange.active)
        self.exchange.price(str(activation));self.assertTrue(self.exchange.active)
        self.exchange.price(str(activation+D('50')))
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(restarted.reconcile(self.tid)['state'],'PROTECTED')
        boundary=self.exchange.extreme*(1-D(request['callbackRate']))
        self.exchange.price(str(boundary))
        result=restarted.reconcile(self.tid)
        self.assertEqual(result['state'],'CLOSED',result)
        self.assertTrue(result['detail']['targetMetBeforeFunding'])
        self.assertEqual(len([c for c in self.exchange.calls if c[0]==OPERATION]),1)
    def test_short_trailing_follows_lows_and_exits_on_bounce(self):
        self.plan['orderPreview'].update(side='SELL',positionSide='SHORT')
        self.item=self.engine.prepare('short-trailing',self.plan);self.tid=self.item['id']
        self.start();self.assertEqual(self.engine.reconcile(self.tid)['state'],'PROTECTED')
        owned=self.engine.get(self.tid)['owned'];request=owned['tpRequest']
        activation=D(request['activatePrice']);self.assertEqual(activation,D(owned['fixedNetTargetPrice']))
        self.exchange.price(str(activation));self.exchange.price(str(activation-D('30')))
        self.exchange.price(str(self.exchange.extreme*(1+D(request['callbackRate']))))
        result=self.engine.reconcile(self.tid);self.assertEqual(result['state'],'CLOSED',result)
        self.assertTrue(result['detail']['targetMetBeforeFunding'])
    def test_lost_ack_reconciles_without_resending_after_restart(self):
        self.exchange.fail='trailing';self.start()
        self.assertEqual(self.engine.writes(self.tid)['TP']['state'],'UNKNOWN')
        engine=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(engine.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(len([c for c in self.exchange.calls if c[0]==OPERATION]),1)

    def test_live_worker_parallel_snapshot_recovers_and_confirms_native_close(self):
        from weex_live_worker import Lifecycle as LiveLifecycle,protected_unchanged
        self.engine=LiveLifecycle(self.path,self.exchange,lambda:self.cfg)
        self.start();result=self.engine.reconcile(self.tid)
        self.assertEqual(result['state'],'PROTECTED',result)
        raw=self.exchange.trailing[0];rows=(self.exchange.positions,[],[normalize(raw)])
        self.assertTrue(protected_unchanged(self.engine,self.tid,rows,now()))
        changed=copy.deepcopy(rows);changed[2][0]['callbackRate']='.005'
        self.assertFalse(protected_unchanged(self.engine,self.tid,changed,now()))
        self.assertFalse(protected_unchanged(self.engine,self.tid,rows,now()-6000))
        self.exchange.price(raw['activatePrice'])
        self.exchange.price(str(self.exchange.extreme*(1-D(raw['callbackRate']))))
        self.assertFalse(protected_unchanged(self.engine,self.tid,([],[],[]),now()))
        result=self.engine.reconcile(self.tid)
        self.assertEqual(result['state'],'CLOSED',result)

    def test_missing_callback_is_not_certified_by_auditor(self):
        from protection_coverage_v2 import coverage
        self.start();raw=self.exchange.trailing[0];del raw['callbackRate']
        self.assertFalse(coverage(self.exchange.positions[0],[],[raw],True)['verified'])
    def test_missing_unknown_order_does_not_retry(self):
        self.exchange.fail='trailing';self.start();self.exchange.trailing=[]
        for _ in range(2):self.engine.reconcile(self.tid)
        self.assertEqual(len([c for c in self.exchange.calls if c[0]==OPERATION]),1)
    def test_rejected_trailing_requires_review(self):
        self.exchange.fail='reject_trailing'
        self.assertEqual(self.start()['state'],'REVIEW_REQUIRED')
    def test_changed_callback_or_activation_is_not_protected(self):
        self.start();self.exchange.trailing[0]['callbackRate']='0.02'
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
    def test_partial_exit_is_not_claimed_closed(self):
        self.start();self.exchange.history=[dict(self.exchange.trailing[0],status='FILLED')]
        self.exchange.trailing=[]
        result=self.engine.reconcile(self.tid)
        self.assertEqual(result['state'],'REVIEW_REQUIRED')
        self.assertIn('EXIT_PARTIAL',result['detail']['reason'])
    def test_existing_fixed_plan_does_not_turn_into_trailing_on_restart(self):
        fixed=copy.deepcopy(self.plan);fixed.pop('exitPolicy')
        self.cfg['strategySettings']['tpMode']='fixed'
        self.item=self.engine.prepare('fixed-first',fixed);self.tid=self.item['id']
        self.plan=fixed;self.start();self.cfg['strategySettings']['tpMode']='trailing'
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(self.engine.writes(self.tid)['TP']['operation'],'post_capi_v3_placeTpSlOrder')
    def test_mode_change_before_entry_blocks(self):
        self.cfg['strategySettings']['tpMode']='fixed'
        result=self.start();self.assertEqual(result['state'],'PREFLIGHT_BLOCKED')
        self.assertEqual(self.exchange.calls,[])
    def test_no_existing_position_adoption(self):
        bad=copy.deepcopy(self.plan);bad['beforePositions']=[{'symbol':'ETHUSDT'}]
        with self.assertRaisesRegex(ValueError,'PREEXISTING_POSITION'):self.engine.prepare('foreign',bad)
    def test_sdk_serialization_exact_and_offline(self):
        self.start();request=self.engine.get(self.tid)['owned']['tpRequest']
        result=prepare_sdk_request(OPERATION,request)
        self.assertTrue(result['sdkSerializationVerified']);self.assertEqual(result['networkRequests'],0)
    def test_capacity_counts_position_once_not_its_closing_trailing(self):
        self.start();order=normalize(self.exchange.trailing[0])
        self.assertTrue(full_closing_tp(order,self.exchange.positions))
        cap=account_capacity(self.exchange.positions,[order],{'77'})
        self.assertEqual(cap['count'],1);self.assertEqual(cap['excludedClosingTPs'],1)
    def test_opening_trailing_is_not_exit_coverage(self):
        self.start();order=self.exchange.trailing[0];order['reduceOnly']=False
        self.assertFalse(full_closing_tp(order,self.exchange.positions))
    def test_exact_identity_required_for_matching(self):
        self.start();request=self.engine.get(self.tid)['owned']['tpRequest'];row=normalize(self.exchange.trailing[0])
        self.assertTrue(matches_request(row,request));row['clientAlgoId']='foreign'
        self.assertFalse(matches_request(row,request))
    def test_atr_policy_units_bounds_and_staleness(self):
        self.assertEqual(entry_policy(signal('0.3'),'10')['callbackRate'],'0.0030')
        self.assertEqual(entry_policy(signal('0.01'),'10')['callbackRate'],'0.0010')
        self.assertEqual(entry_policy(signal('8'),'10')['callbackRate'],'0.0100')
        old=signal();old['closedCandleTimes']['5m']=now()-400000
        with self.assertRaisesRegex(ValueError,'STALE'):entry_policy(old,'10')
        for invalid in ('0','NaN','Infinity','-1'):
            with self.assertRaises(ValueError):entry_policy(signal(invalid),'10')
    def test_buffer_preserves_fixed_net_price_at_first_callback_for_both_sides(self):
        for side in ('LONG','SHORT'):
            fixed={'symbol':'ETHUSDT','positionSide':side,'reduceOnly':True,
                   'quantity':'1','triggerPrice':'100','clientAlgoId':'exit'}
            req=request_from_fixed_tp(fixed,{'callbackRate':'.003'},'.01')
            boundary=D(req['activatePrice'])*(1-D('.003') if side=='LONG' else 1+D('.003'))
            self.assertTrue(boundary>=100 if side=='LONG' else boundary<=100)

    def test_new_policies_activate_at_net_target_without_buffer_for_both_sides(self):
        for target in ('10','20'):
            policy=entry_policy(signal(),target)
            self.assertEqual(policy['activationMode'],'AT_NET_TARGET')
            for side in ('LONG','SHORT'):
                fixed={'symbol':'ETHUSDT','positionSide':side,'reduceOnly':True,
                       'quantity':'1','triggerPrice':'100','clientAlgoId':'exit'}
                req=request_from_fixed_tp(fixed,policy,'.01')
                self.assertEqual(D(req['activatePrice']),D(fixed['triggerPrice']))

    def test_immediate_pullback_can_close_below_activation_target(self):
        self.start();req=self.engine.get(self.tid)['owned']['tpRequest']
        self.exchange.price(req['activatePrice'])
        self.exchange.price(str(self.exchange.extreme*(1-D(req['callbackRate']))))
        result=self.engine.reconcile(self.tid)
        self.assertEqual(result['state'],'CLOSED')
        self.assertFalse(result['detail']['targetMetBeforeFunding'])

    def test_twenty_usdt_setting_activates_at_twenty_net_after_estimated_fees(self):
        self.cfg['strategySettings']['targetNetProfitUSDT']='20'
        self.plan['targetNetProfitUSDT']='20'
        self.plan['exitPolicy']=entry_policy(signal(),'20')
        self.item=self.engine.prepare('twenty-net',self.plan);self.tid=self.item['id']
        self.start();owned=self.engine.get(self.tid)['owned']
        price=D(owned['tpRequest']['activatePrice']);qty=D(owned['quantity'])
        net=qty*price-D(owned['actualEntryCostUSDT'])-D(owned['actualEntryFeesUSDT'])-qty*price*D(self.plan['exitFeeRate'])
        self.assertGreaterEqual(net,D('20'))
        self.assertLess(net,D('20')+qty*D(self.plan['sizing']['priceTick']))

    def test_existing_buffered_plan_recovers_with_original_activation(self):
        self.plan['exitPolicy'].pop('activationMode')
        self.item=self.engine.prepare('legacy-buffered',self.plan);self.tid=self.item['id']
        self.start();owned=self.engine.get(self.tid)['owned']
        self.assertGreater(D(owned['tpRequest']['activatePrice']),D(owned['fixedNetTargetPrice']))
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(restarted.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(restarted.get(self.tid)['owned']['tpRequest'],owned['tpRequest'])
    def test_duplicate_trailing_observations_rejected(self):
        self.start();row=self.exchange.trailing[0]
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):merge([],[row,row])
    def test_gateway_accepts_only_durable_exact_trailing_exit(self):
        from weex_live_worker import Gateway,SCOPE,HOST
        self.start();item=self.engine.get(self.tid);item['plan']['liveAuthorizationScope']=SCOPE
        item['plan']['authorization']={'host':HOST,'generation':1,'configHash':'test'}
        request=item['owned']['tpRequest'];gateway=Gateway(Path(self.tmp.name),None);gateway.current=self.tid
        from unittest.mock import Mock
        gateway.engine=Mock();gateway.engine.get.return_value=item
        gateway.engine.writes.return_value={'TP':{'state':'UNKNOWN','payload':request}}
        self.assertEqual(gateway.validate(OPERATION,request)[0],'TP')
        wrong=dict(request,reduceOnly=False)
        with self.assertRaises(PermissionError):gateway.validate(OPERATION,wrong)

    def test_gateway_real_sdk_uses_exact_native_endpoint_and_budget(self):
        from unittest.mock import Mock,MagicMock
        from weex_live_worker import Gateway,SCOPE,HOST
        from weex_api_budget import Budget
        self.start();item=self.engine.get(self.tid)
        item['plan'].update(liveAuthorizationScope=SCOPE,authorization={'host':HOST})
        request=item['owned']['tpRequest'];root=Path(self.tmp.name)
        (root/'weex_credentials.json').write_text(json.dumps({'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
        b=Budget(root);b.install_rate_limits([{'rateLimitType':'REQUEST_WEIGHT','interval':'MINUTE','intervalNum':1,'limit':100},
            {'rateLimitType':'ORDERS','interval':'MINUTE','intervalNum':1,'limit':20}])
        gateway=Gateway(root,None);gateway.current=self.tid;gateway.engine=Mock()
        gateway.engine.get.return_value=item;gateway.engine.writes.return_value={'TP':{'state':'UNKNOWN','payload':request}}
        network=MagicMock();network.__enter__.return_value=network
        network.request.return_value=Mock(status_code=200,headers={},text=json.dumps({'success':True,'orderId':'2'}))
        with patch('requests.Session',return_value=network),patch('weex_live_worker.budget',return_value=b):
            result=gateway.write(OPERATION,request)
        self.assertTrue(result['success']);network.request.assert_called_once()
        call=network.request.call_args
        self.assertEqual(call.args,('POST',HOST+'/capi/v3/algoOrder'))
        self.assertEqual(json.loads(call.kwargs['data']),request)
        self.assertFalse(call.kwargs['allow_redirects'])
        self.assertEqual(b.used()['orders'],1)
        self.assertEqual(b.reserve('GET',HOST+'/capi/v3/trailing/historyOrders'),10)

    def test_native_trailing_coverage_and_open_report(self):
        from protection_coverage_v2 import coverage
        from weex_position_reports import open_rows
        self.start();p=dict(self.exchange.positions[0],asset='USDT',leverage='100',openValue='50')
        raw=self.exchange.trailing[0]
        report=coverage(p,[],[raw],True)
        self.assertTrue(report['verified']);self.assertTrue(report['trailingCovered'])
        self.assertFalse(report['tpCovered']);self.assertFalse(report['slCovered'])
        row=open_rows([p],[],[raw])[0]
        self.assertIn('Trailing:',row['tp'][0]);self.assertIn('rientro 0.3000%',row['tp'][0])

    def test_closed_quality_understands_activation_target_trailing(self):
        from weex_closed_quality import audit
        self.start();req=self.engine.get(self.tid)['owned']['tpRequest']
        self.exchange.price(req['activatePrice']);self.exchange.price(str(self.exchange.extreme*(1-D(req['callbackRate']))))
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'CLOSED')
        item=self.engine.get(self.tid);plan=item['plan'];plan['actualCrossLeverage']='100'
        plan['sizing']['quantityStep']='0.001'
        from contextlib import closing
        with closing(self.engine.db()) as c,c:
            c.execute('UPDATE trades_v1 SET plan=? WHERE id=?',(json.dumps(plan),self.tid))
        # Audit expects the production basename; copy only the isolated test journal.
        import shutil
        root=Path(self.tmp.name);shutil.copy2(self.path,root/'weex_user_live_lifecycle.sqlite3')
        result=audit(root);row=result['trades'][0]
        self.assertEqual(row['exitMode'],'TRAILING')
        self.assertEqual(row['auditStatus'],'ECONOMICS_CHECKED_FUNDING_EXCLUDED',result)
        self.assertFalse(any(f['code']=='BOT_TP_PARAMETERS' for f in result['findings']))
        self.assertEqual(row['targetRole'],'TRAILING_ACTIVATION')
        self.assertFalse(row['targetMetBeforeFunding'])
        self.assertFalse(any(f['code']=='TARGET_NOT_REACHED' for f in result['findings']))

    def test_manual_capture_fetches_atr_and_freezes_native_exit_policy(self):
        import weex_live_worker as worker
        from unittest.mock import Mock
        root=Path(self.tmp.name);reader=Mock(root=root);reader.account.return_value=([],[],[])
        values={'get_capi_v3_account_commissionRate':{},'get_capi_v3_account_symbolConfig':[
            {'symbol':'ETHUSDT','separatedType':'COMBINED'}],
            'get_capi_v3_account_accountConfig':{'canTrade':True,'dualSidePosition':True},
            'get_capi_v3_account_balance':[{'asset':'USDT','availableBalance':'100'}]}
        reader.read.side_effect=lambda op,**q:values[op]
        market_signal=signal();market_signal.update(decision='WAIT',reasons=[])
        book={'status':'OK','bestBid':'2499','bestAsk':'2500','depthUnitVerified':True,'passed':True}
        metadata={'/capi/v3/market/exchangeInfo':{'symbols':[{'symbol':'ETHUSDT','forwardContractFlag':True}]},
                  '/capi/v3/market/riskLimits':[{'symbol':'ETHUSDT','brackets':[]}],
                  '/capi/v3/market/apiTradingSymbols':['ETHUSDT']}
        preview=dict(self.plan,status='BLOCKED_PREVIEW',publicRiskTierVerified=True)
        with patch.object(worker,'analyze',return_value=market_signal) as analyzer,\
             patch.object(worker,'inspect',return_value=book),patch.object(worker,'public',side_effect=lambda path,**kw:metadata[path]),\
             patch.object(worker,'apply_book_gate',return_value={'realOrderBook':book}),\
             patch.object(worker,'preview',return_value=preview),patch.object(worker,'capacity',return_value={'count':0}):
            plan,ctx,_=worker.capture(reader,'ETHUSDT',self.cfg,manual_side='LONG',manual_request_id='test')
        analyzer.assert_called_once_with('ETHUSDT')
        self.assertEqual(plan['exitPolicy']['callbackRate'],'0.0030')
        self.assertEqual(plan['entrySource'],'manual_telegram')
        self.assertEqual(ctx['marketSignal'],'LONG')

class TrailingMenuTests(unittest.TestCase):
    def test_selecting_trailing_stops_entries_and_amount_editor_preserves_mode(self):
        import commands,telegram_ai_fullmenu as menu,telegram_ai_settings as settings,live_control
        from contextlib import ExitStack,closing
        cfg=json.loads(Path(__file__).with_name('weex_ai_risk_config.json').read_text(encoding='utf-8'))
        class EndLoop(Exception):pass
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'weex_ai_risk_config.json';config.write_text(json.dumps(cfg))
            tg=root/'telegram.json';tg.write_text(json.dumps({'telegram_bot_token':'DUMMY','telegram_chat_id':'1','telegram_user_id':'1'}))
            live_control.state(root)
            with closing(live_control.connect(root)) as c,c:c.execute("UPDATE switch_v1 SET mode='RUNNING'")
            replies=[]
            def tick(choice):
                connections=[];original_connect=commands.sqlite3.connect
                def tracked_connect(*a,**kw):
                    connection=original_connect(*a,**kw);connections.append(connection);return connection
                update={'update_id':1,'callback_query':{'id':'test','from':{'id':1},
                    'message':{'chat':{'id':1}},'data':choice}}
                def api(token,method,args):
                    if method=='getUpdates':return [update]
                    if method=='sendMessage':replies.append(args)
                    return True
                with ExitStack() as stack:
                    stack.enter_context(patch.object(commands.sqlite3,'connect',side_effect=tracked_connect))
                    for target,field,value in ((commands,'ROOT',root),(commands,'DB',root/'commands.sqlite3'),
                            (commands,'TG',tg),(menu,'P',config),(settings,'CONFIG',config)):
                        stack.enter_context(patch.object(target,field,value))
                    stack.enter_context(patch.object(commands,'api',side_effect=api))
                    stack.enter_context(patch.object(commands.time,'sleep',side_effect=EndLoop))
                    with self.assertRaises(EndLoop):commands.main()
                for connection in connections:connection.close()
            tick('aitpmode:trailing')
            self.assertEqual(json.loads(config.read_text())['strategySettings']['tpMode'],'trailing')
            self.assertEqual(live_control.state(root)['mode'],'STOPPED')
            self.assertTrue(any(b['callback_data']=='livectl:start' for r in replies
                                for row in r.get('reply_markup',{}).get('inline_keyboard',[]) for b in row))
            tick('aitpmode:amount')
            self.assertEqual(json.loads(config.read_text())['strategySettings']['tpMode'],'trailing')
            with patch.object(menu,'P',config):
                labels=[b['text'] for row in menu.tp_modes_menu()['inline_keyboard'] for b in row]
            self.assertIn('✅ TP netto + trailing WEEX',labels)

    def test_live_config_accepts_trailing_but_keeps_other_models_blocked(self):
        import live_control
        cfg=json.loads(Path(__file__).with_name('weex_ai_risk_config.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'weex_ai_risk_config.json'
            cfg['strategySettings']['tpMode']='trailing'
            cfg['strategySettings']['tpAccountingMode']='NET'
            path.write_text(json.dumps(cfg))
            self.assertEqual(live_control.configuration(root)[0]['strategySettings']['tpMode'],'trailing')
            cfg['strategySettings']['tpMode']='dynamic';path.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'UNSUPPORTED_STRATEGY'):live_control.configuration(root)

if __name__=='__main__':unittest.main()
