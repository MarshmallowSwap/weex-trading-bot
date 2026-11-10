import copy,json,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock,patch
from weex_lifecycle import Lifecycle,now
from weex_http_guard import prepare_sdk_request,ScopedTradingSession
from weex_http_guard import sdk_types
from weex_lifecycle import SDKGateway
from urllib.parse import urlsplit,parse_qs

CFG={'execution':{'enabled':True,'mode':'LIVE','allowOrdersWithoutStop':True},
     'risk':{'stopLoss':{'enabled':False},'initialMarginTargetUSDT':5},
     'strategySettings':{'targetNetProfitUSDT':1},
     'telegramSettings':{'maxConcurrentPositions':{'default':2}}}
PLAN={'orderPreview':{'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
      'quantity':'0.02','newClientOrderId':'preview','tpTriggerPrice':'2555','TpWorkingType':'MARK_PRICE'},
      'beforePositions':[],'requestedLeverage':'100','requiredMarginAndEntryFeeUSDT':'5.04',
      'targetNetProfitUSDT':'1','exitFeeRate':'0.0008',
      'sizing':{'notionalUSDT':'50','priceTick':'0.01'}}


class Exchange:
    """Local fixture only. No credentials, HTTP sessions or network calls."""
    def __init__(self):
        self.calls=[];self.order=None;self.trades=[];self.positions=[];self.algos=[]
        self.margin='CROSSED';self.leverage='100';self.fail=None;self.partial=False;self.cancelled=False
    def write(self,op,p):
        self.calls.append((op,copy.deepcopy(p)))
        if op=='post_capi_v3_account_marginType':self.margin=p['marginType'];return {'marginType':self.margin}
        if op=='post_capi_v3_account_leverage':self.leverage=p['crossLeverage'];return {'crossLeverage':self.leverage}
        if op=='delete_capi_v3_order':
            self.cancelled=True;self.order['status']='CANCELED';return {'success':True,'orderId':'1'}
        if op=='post_capi_v3_order':
            qty='0.01' if self.partial else p['quantity']
            self.order={**p,'orderId':'1','clientOrderId':p['newClientOrderId'],
                        'executedQty':qty,'status':'PARTIALLY_FILLED' if self.partial else 'FILLED'}
            self.trades=[{'id':'11','orderId':'1','symbol':p['symbol'],'side':p['side'],'positionSide':p['positionSide'],
                          'qty':qty,'price':'2500','commission':'0.04','commissionAsset':'USDT'}]
            self.positions=[{'id':'77','symbol':p['symbol'],'side':p['positionSide'],'size':qty}]
            if self.fail=='entry':raise TimeoutError()
            return {'success':True,'orderId':'1','clientOrderId':p['newClientOrderId']}
        if op=='post_capi_v3_placeTpSlOrder':
            self.algos=[{'algoId':'2','clientAlgoId':p['clientAlgoId'],'symbol':p['symbol'],
               'positionSide':p['positionSide'],'side':'SELL' if p['positionSide']=='LONG' else 'BUY',
               'orderType':'TAKE_PROFIT_MARKET','reduceOnly':True,'quantity':p['quantity'],
               'triggerPrice':p['triggerPrice'],'workingType':p['triggerPriceType'],'algoStatus':'UNTRIGGERED'}]
            if self.fail=='tp':raise TimeoutError()
            return [{'success':True,'orderId':'2'}]
        raise AssertionError('UNEXPECTED_WRITE')
    def read(self,op,**q):
        if op=='get_capi_v3_openOrders':return [copy.deepcopy(self.order)] if self.order and self.order['status']=='PARTIALLY_FILLED' else []
        if op=='get_capi_v3_order_history':return [copy.deepcopy(self.order)] if self.order else []
        if op=='get_capi_v3_order':
            if str(q['orderId'])=='3':return {'orderId':'3','symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
                                             'reduceOnly':True,'status':'FILLED','executedQty':self.order['executedQty']}
            return copy.deepcopy(self.order)
        if op=='get_capi_v3_userTrades':
            if str(q['orderId'])=='3':return [{'id':'13','orderId':'3','symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
                 'qty':self.order['executedQty'],'price':self.algos[0]['triggerPrice'],'commission':'0.04','commissionAsset':'USDT'}]
            return copy.deepcopy(self.trades)
        if op=='get_capi_v3_account_position_allPosition':return copy.deepcopy(self.positions)
        if op=='get_capi_v3_openAlgoOrders':return copy.deepcopy([a for a in self.algos if a['algoStatus']=='UNTRIGGERED'])
        if op=='get_capi_v3_allAlgoOrders':return {'orders':copy.deepcopy(self.algos),'hasMore':False}
        raise AssertionError('UNEXPECTED_READ '+op)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'runtime.db';self.exchange=Exchange();self.cfg=copy.deepcopy(CFG)
        self.engine=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.trade=self.engine.prepare('closed-candle-1',PLAN);self.tid=self.trade['id']
    def ctx(self,symbol):
        return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,'hedgeMode':True,
         'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
         'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
         'symbolConfig':{'symbol':symbol,'marginType':self.exchange.margin,'crossLeverage':self.exchange.leverage},
         'referencePrice':'2500','exitFeeRate':'0.0008','maximumPermittedLeverage':'100'}
    def entry(self):return self.engine.advance(self.tid,self.ctx)
    def test_pretrade_mode_stops_before_reading_or_writing(self):
        self.cfg['execution'].update(enabled=False,mode='PRETRADE')
        provider=Mock(side_effect=AssertionError())
        self.assertEqual(self.engine.advance(self.tid,provider)['state'],'STOP_BEFORE_SUBMISSION')
        self.assertEqual(self.exchange.calls,[]);provider.assert_not_called()
        self.assertEqual(self.engine.writes(self.tid),{})
    def test_sdk_serializes_entry_tp_and_account_settings_without_network(self):
        for r in self.trade['plan']['setupRequests']:
            self.assertEqual(prepare_sdk_request(r['operation'],r['payload'])['networkRequests'],0)
        self.entry();tp=self.engine.get(self.tid)['owned']['tpRequest']
        self.assertEqual(prepare_sdk_request('post_capi_v3_placeTpSlOrder',tp)['networkRequests'],0)
        self.assertFalse(tp['closePosition']);self.assertTrue(tp['reduceOnly'])
        self.assertNotIn('tpTriggerPrice',self.trade['plan']['entry'])
    def test_entry_tp_protection_and_close_full_lifecycle(self):
        self.assertEqual(self.entry()['state'],'TP_PENDING')
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'PROTECTED')
        self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'CLOSED')
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(restarted.reconcile(self.tid)['state'],'CLOSED')
        self.assertEqual(len(self.exchange.calls),2)
    def test_setup_is_confirmed_by_readback_before_entry(self):
        self.exchange.margin='ISOLATED';self.exchange.leverage='20'
        self.entry()
        self.assertEqual([x[0] for x in self.exchange.calls],['post_capi_v3_account_marginType',
            'post_capi_v3_account_leverage','post_capi_v3_order','post_capi_v3_placeTpSlOrder'])
    def test_setup_not_confirmed_never_opens(self):
        self.exchange.margin='ISOLATED'
        with patch.object(self.exchange,'write',return_value={'marginType':'CROSSED'}) as write:
            self.assertEqual(self.entry()['state'],'ACCOUNT_SETUP_UNCONFIRMED')
            self.entry();self.assertEqual(write.call_count,1)
    def test_entry_timeout_recovers_no_duplicate(self):
        self.exchange.fail='entry';self.entry()
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(restarted.advance(self.tid,self.ctx)['state'],'PROTECTED')
        self.assertEqual(sum(op=='post_capi_v3_order' for op,p in self.exchange.calls),1)
    def test_tp_timeout_recovers_by_saved_client_identifier(self):
        self.exchange.fail='tp';self.entry()
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(sum(op=='post_capi_v3_placeTpSlOrder' for op,p in self.exchange.calls),1)
    def test_missing_order_after_unknown_never_retries(self):
        with patch.object(self.exchange,'write',side_effect=TimeoutError()) as write:
            self.entry();self.entry();self.assertEqual(write.call_count,1)
        self.assertEqual(self.engine.get(self.tid)['state'],'REVIEW_REQUIRED')
    def test_crash_persists_unknown_before_sdk_call(self):
        def crash(op,p):
            self.assertEqual(Lifecycle(self.path,self.exchange,lambda:self.cfg).writes(self.tid)['ENTRY']['state'],'UNKNOWN')
            raise KeyboardInterrupt()
        with patch.object(self.exchange,'write',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.entry()
        self.entry();self.assertEqual(self.exchange.calls,[])
    def test_partial_entry_cancel_confirm_then_tp_actual_quantity(self):
        self.exchange.partial=True
        self.assertEqual(self.entry()['state'],'ENTRY_PENDING')
        self.assertTrue(self.exchange.cancelled)
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'TP_PENDING')
        self.assertEqual(self.engine.get(self.tid)['owned']['tpRequest']['quantity'],'0.01')
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'PROTECTED')
    def test_tp_uses_actual_entry_fees_and_exit_fee(self):
        self.entry();own=self.engine.get(self.tid)['owned'];q=Decimal(own['quantity']);price=Decimal(own['tpRequest']['triggerPrice'])
        net=q*price-Decimal(own['actualEntryCostUSDT'])-Decimal(own['actualEntryFeesUSDT'])-q*price*Decimal('0.0008')
        self.assertGreaterEqual(net,1)
    def test_manual_or_unrelated_position_increase_blocks_tp(self):
        original=self.exchange.write
        def write(op,p):
            response=original(op,p)
            if op=='post_capi_v3_order':self.exchange.positions[0]['size']='0.03'
            return response
        with patch.object(self.exchange,'write',side_effect=write):self.entry()
        self.assertEqual(self.engine.get(self.tid)['state'],'REVIEW_REQUIRED')
        self.assertEqual(len(self.exchange.calls),1)
    def test_phase_two_rejects_changed_position_cost_before_tp(self):
        original=self.exchange.write
        def write(op,p):
            response=original(op,p)
            if op=='post_capi_v3_order':
                self.exchange.positions[0]['openValue']='999'
                self.exchange.positions[0]['openFee']='0.04'
            return response
        with patch.object(self.exchange,'write',side_effect=write):
            self.entry()
        item=self.engine.get(self.tid)
        self.assertEqual(item['state'],'REVIEW_REQUIRED')
        self.assertEqual(item['detail']['reason'],'POSITION_ECONOMICS_CHANGED_BEFORE_TP')
        self.assertEqual([x[0] for x in self.exchange.calls],['post_capi_v3_order'])
    def test_two_phase_keeps_pnl_audit_from_fills(self):
        self.entry()
        owned=self.engine.get(self.tid)['owned']
        self.assertEqual(owned['tpPnlPreview']['mode'],'PNL_NET_USDT')
        self.assertEqual(owned['tpPnlPreview']['triggerPrice'],owned['tpRequest']['triggerPrice'])
        self.assertEqual(owned['actualEntryCostUSDT'],'50.00')
    def test_tp_ack_id_must_match_observed_id(self):
        self.entry();self.exchange.algos[0]['algoId']='other'
        self.assertEqual(self.engine.reconcile(self.tid)['detail']['reason'],'TP_ACK_CONTRADICTS_HISTORY')
    def test_tp_canceled_never_recreated(self):
        self.entry();self.exchange.algos[0]['algoStatus']='CANCELED'
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
        self.assertEqual(len(self.exchange.calls),2)
    def test_position_disappearance_is_not_tp_closure(self):
        self.entry();self.exchange.positions=[]
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
    def test_duplicate_or_non_usdt_fills_block(self):
        for field in ('duplicate','currency'):
            with self.subTest(field=field):
                ex=Exchange();eng=Lifecycle(Path(self.temp.name)/(field+'.db'),ex,lambda:self.cfg);tid=eng.prepare(field,PLAN)['id']
                original=ex.write
                def write(op,p):
                    response=original(op,p)
                    if op=='post_capi_v3_order':
                        if field=='duplicate':ex.trades*=2
                        else:ex.trades[0]['commissionAsset']='BTC'
                    return response
                with patch.object(ex,'write',side_effect=write):eng.advance(tid,self.ctx)
                self.assertEqual(eng.get(tid)['state'],'REVIEW_REQUIRED')
    def test_unverified_liquidity_stale_state_and_occupied_symbol_block(self):
        for change in ({'depthUnitVerified':False},{'observedAtMs':now()-6000},
                       {'conditionalOrders':[{'symbol':'ETHUSDT'}]},{'referencePrice':'2510'},
                       {'exitFeeRate':'0.001'},{'hedgeMode':False},{'complete':False}):
            with self.subTest(change=change):
                self.assertEqual(self.engine.advance(self.tid,lambda s:{**self.ctx(s),**change})['state'],'PREFLIGHT_BLOCKED')
        self.assertEqual(self.exchange.calls,[])
    def test_prepare_cannot_replace_existing_exposure_lifecycle(self):
        self.entry()
        with self.assertRaisesRegex(ValueError,'UNRESOLVED'):self.engine.prepare('new',PLAN)
    def test_unsent_preview_superseded_without_any_write(self):
        second=self.engine.prepare('new',PLAN)
        self.assertEqual(self.engine.get(self.tid)['state'],'SUPERSEDED')
        self.assertEqual(second['state'],'PREPARED');self.assertEqual(self.exchange.calls,[])
        self.assertEqual(self.engine.advance(self.tid,self.ctx)['state'],'SUPERSEDED')
        self.assertEqual(self.exchange.calls,[])
    def test_readback_failure_does_not_reach_entry(self):
        self.exchange.margin='ISOLATED'
        provider=Mock(side_effect=[self.ctx('ETHUSDT'),TimeoutError()])
        self.assertEqual(self.engine.advance(self.tid,provider)['state'],'ACCOUNT_SETUP_UNCONFIRMED')
        self.assertEqual([x[0] for x in self.exchange.calls],['post_capi_v3_account_marginType'])
    def test_short_tp_rounds_to_recover_actual_fees(self):
        plan=copy.deepcopy(PLAN);plan['orderPreview'].update(side='SELL',positionSide='SHORT',tpTriggerPrice='2440')
        eng=Lifecycle(Path(self.temp.name)/'short.db',self.exchange,lambda:self.cfg)
        tid=eng.prepare('short',plan)['id']
        eng.advance(tid,lambda s:{**self.ctx(s),'marketSignal':'SHORT'})
        own=eng.get(tid)['owned'];q=Decimal(own['quantity']);price=Decimal(own['tpRequest']['triggerPrice'])
        net=Decimal(own['actualEntryCostUSDT'])-q*price-Decimal(own['actualEntryFeesUSDT'])-q*price*Decimal('0.0008')
        self.assertGreaterEqual(net,1)
        self.assertEqual(eng.reconcile(tid)['state'],'PROTECTED')
    def test_real_sdk_and_scoped_http_transport_complete_local_fixture_flow(self):
        config,contract,operations=sdk_types()
        lookup={(v['method'],v['path']):k for k,v in operations.items()}
        network=Mock()
        def request(method,url,**kw):
            parsed=urlsplit(url);op=lookup[(method,parsed.path)]
            query={k:v[0] for k,v in parse_qs(parsed.query).items()}
            if method=='GET':data=self.exchange.read(op,**query)
            else:
                payload=json.loads(kw['data']) if kw.get('data') else {'query':query}
                data=self.exchange.write(op,payload)
            return Mock(status_code=200,headers={},text=json.dumps(data))
        network.request.side_effect=request
        # Keep this HTTP fixture independent of the shared real quota database;
        # quota behavior is covered by dedicated governor tests.
        with patch('requests.Session',return_value=network), patch(
                'weex_api_budget.request',
                side_effect=lambda session,method,url,**kw: session.request(method,url,**kw)):
            transport=ScopedTradingSession(lambda:self.cfg,lambda request:True)
            sdk=contract(config_rest_api=config(base_path='https://api-contract.weex.com',api_key='DUMMY',
                api_secret='DUMMY',passphrase='DUMMY',session=transport,max_retries=0))
            eng=Lifecycle(Path(self.temp.name)/'sdk.db',SDKGateway(sdk),lambda:self.cfg)
            tid=eng.prepare('sdk',PLAN)['id']
            self.assertEqual(eng.advance(tid,self.ctx)['state'],'TP_PENDING')
            self.assertEqual(eng.reconcile(tid)['state'],'PROTECTED')
            self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
            self.assertEqual(eng.reconcile(tid)['state'],'CLOSED')
        self.assertEqual(sum(c.args[0]=='POST' for c in network.request.call_args_list),2)
    def test_capacity_is_reserved_atomically_at_dispatch(self):
        self.cfg['telegramSettings']['maxConcurrentPositions']['default']=1
        self.entry()
        plan=copy.deepcopy(PLAN);plan['orderPreview']['symbol']='BTCUSDT'
        other=self.engine.prepare('other-symbol',plan)['id']
        result=self.engine.send_once(other,'ENTRY','post_capi_v3_order',self.engine.get(other)['plan']['entry'],capacity={'count':0,'symbols':[]})
        self.assertEqual(result['state'],'CAPACITY_RESERVED_BY_OTHER_ENTRY')


class DepthEvidenceTests(unittest.TestCase):
    def test_cross_source_agreement_does_not_claim_unit_certification(self):
        from weex_depth_unit_audit import assess
        result=assess('ETHUSDT',{'symbol':'ETHUSDT','contractVal':'0.001'},
            {'bids':[['2500','2.1']],'asks':[['2501','2.2']]},
            {'symbol':'ETHUSDT','bidPrice':'2500','bidQty':'2.1','askPrice':'2501','askQty':'2.2'},
            [{'price':'2500','qty':'0.002','quoteQty':'5'}])
        self.assertTrue(result['tradeQuoteEqualsPriceTimesBaseQty'])
        self.assertTrue(all(result['bookTickerExactMatches'].values()))
        self.assertFalse(result['depthUnitVerified'])
        self.assertNotEqual(result['notionalScenarios']['bids']['ifSizeIsBaseAssetUSDT'],result['notionalScenarios']['bids']['ifSizeIsContractsUSDT'])


class ScopedTransportTests(unittest.TestCase):
    def test_live_flag_without_request_authorizer_still_blocks(self):
        with patch('requests.Session') as session:
            transport=ScopedTradingSession(lambda:CFG,None)
            with self.assertRaises(PermissionError):transport.request('POST','https://api-contract.weex.com/capi/v3/order',data=b'{}')
            session.return_value.request.assert_not_called()
    def test_pretrade_cannot_be_overridden_by_authorizer(self):
        cfg=copy.deepcopy(CFG);cfg['execution']['mode']='PRETRADE'
        with patch('requests.Session') as session:
            transport=ScopedTradingSession(lambda:cfg,lambda r:True)
            with self.assertRaises(PermissionError):transport.request('POST','https://api-contract.weex.com/capi/v3/order',data=b'{}')
            session.return_value.request.assert_not_called()
    def test_scope_excludes_close_all_and_transfers(self):
        with patch('requests.Session') as session:
            transport=ScopedTradingSession(lambda:CFG,lambda r:True)
            for path in ('/capi/v3/closePositions','/capi/v3/allOpenOrders','/transfer'):
                with self.assertRaises(PermissionError):transport.request('POST','https://api-contract.weex.com'+path,data=b'{}')
            session.return_value.request.assert_not_called()
    def test_authorization_is_per_exact_request_digest(self):
        with patch('requests.Session') as session:
            session.return_value.request.return_value.status_code=200
            auth=Mock(return_value=True);transport=ScopedTradingSession(lambda:CFG,auth)
            transport.request('POST','https://api-contract.weex.com/capi/v3/order',data=b'{"quantity":"1"}')
            first=auth.call_args.args[0]['sha256']
            transport.request('POST','https://api-contract.weex.com/capi/v3/order',data=b'{"quantity":"2"}')
            self.assertNotEqual(first,auth.call_args.args[0]['sha256'])
            self.assertFalse(session.return_value.request.call_args.kwargs['allow_redirects'])


if __name__=='__main__':unittest.main()
