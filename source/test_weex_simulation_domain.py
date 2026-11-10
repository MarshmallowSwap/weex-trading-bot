import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from contextlib import closing
from weex_simulation_domain import SIM,SimulationSession,SimulationGateway,capture_request,create_runtime,validate_contract,make_client
from weex_lifecycle import Lifecycle,now
from test_weex_lifecycle import Exchange,CFG,PLAN

class GuardTests(unittest.TestCase):
    def test_sdk_read_keeps_simulation_host(self):
        import requests
        with tempfile.TemporaryDirectory() as temp:
            creds=Path(temp)/'dummy.json'
            creds.write_text(json.dumps({'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
            network=Mock()
            response=requests.Response();response.status_code=200;response._content=b'[]'
            network.request.return_value=response
            client=make_client(creds,network)
            result=client.rest_api.execute_operation('get_capi_v3_account_position_allPosition',{'query':{}})
            self.assertEqual(result.data,[])
            self.assertEqual(network.request.call_args.kwargs['url'],SIM+'/capi/v3/account/position/allPosition')
            self.assertFalse(network.request.call_args.kwargs['allow_redirects'])
    def test_production_and_writes_blocked(self):
        network=Mock();guard=SimulationSession(network)
        for method,url in [('POST',SIM+'/capi/v3/order'),('DELETE',SIM+'/capi/v3/order'),
            ('GET','https://api-contract.weex.com/capi/v3/account/balance'),
            ('GET','https://api-sim.weex.com.evil.example/capi/v3/account/balance')]:
            with self.subTest(method=method,url=url),self.assertRaises(PermissionError):guard.request(method,url)
        network.request.assert_not_called()
    def test_redirect_and_failure_no_fallback(self):
        network=Mock();network.request.return_value.status_code=302
        with self.assertRaises(PermissionError):SimulationSession(network).request('GET',SIM+'/capi/v3/account/balance')
        self.assertEqual(network.request.call_count,1)
    def test_get_has_no_body(self):
        network=Mock()
        with self.assertRaises(PermissionError):SimulationSession(network).request('GET',SIM+'/capi/v3/account/balance',json={})
        network.request.assert_not_called()
    def test_false_flag_and_wrong_source_blocked(self):
        meta={'quoteAsset':'USDT','marginAsset':'USDT','forwardContractFlag':False}
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_CONTRACT'):validate_contract(meta,source_host=SIM)
        with self.assertRaises(PermissionError):validate_contract(meta,source_host='https://api-contract.weex.com')
    def test_runtime_forces_pretrade_and_separate_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            ex=Exchange();cfg=copy.deepcopy(CFG)
            engine=create_runtime(temp,ex,cfg)
            tid=engine.prepare('simulation-fixture',PLAN)['id']
            cfg['execution']['enabled']=True
            self.assertEqual(engine.advance(tid,Mock())['state'],'STOP_BEFORE_SUBMISSION')
            self.assertEqual(ex.calls,[])
            self.assertEqual(engine.path.parent.name,'simulation_domain')
            self.assertFalse((Path(temp)/'weex_lifecycle.sqlite3').exists())
    def test_existing_production_journal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'simulation_domain';folder.mkdir()
            with closing(sqlite3.connect(folder/'runtime.sqlite3')) as db,db:db.execute('CREATE TABLE trades_v1(id TEXT)')
            with self.assertRaisesRegex(PermissionError,'UNBOUND_EXISTING_JOURNAL'):create_runtime(temp,Exchange(),CFG)
    def test_other_host_journal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'simulation_domain';folder.mkdir()
            with closing(sqlite3.connect(folder/'runtime.sqlite3')) as db,db:
                db.execute('CREATE TABLE simulation_environment(id INTEGER PRIMARY KEY,host TEXT)')
                db.execute('INSERT INTO simulation_environment VALUES(1,?)',('https://api-contract.weex.com',))
            with self.assertRaises(PermissionError):create_runtime(temp,Exchange(),CFG)
    def test_close_payload_serialized_offline(self):
        p={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET','quantity':'0.02',
           'newClientOrderId':'sim-close-fixture','reduceOnly':True}
        r=capture_request('post_capi_v3_order',p)
        self.assertEqual(r['environment'],SIM);self.assertTrue(r['payload']['reduceOnly']);self.assertEqual(r['networkRequests'],0)

class CapturingExchange(Exchange):
    def write(self,op,payload):
        captured=capture_request(op,payload)
        assert captured['environment']==SIM and captured['networkRequests']==0
        return super().write(op,captured['payload'])

class CycleTests(unittest.TestCase):
    def cycle(self,mode):
        # Synthetic contract/fills only; this does not validate contradictory live metadata.
        with tempfile.TemporaryDirectory() as temp:
            ex=CapturingExchange();ex.partial=mode=='partial'
            if mode=='setup':ex.margin='ISOLATED';ex.leverage='20'
            if mode=='entry_timeout':ex.fail='entry'
            if mode=='tp_timeout':ex.fail='tp'
            cfg=copy.deepcopy(CFG);cfg['telegramSettings']['maxConcurrentPositions']['default']=1
            path=Path(temp)/'offline-fixture.sqlite3'
            engine=Lifecycle(path,ex,lambda:cfg);tid=engine.prepare('offline-'+mode,PLAN)['id']
            def ctx(symbol):
                return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,'hedgeMode':True,
                    'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
                    'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
                    'symbolConfig':{'symbol':symbol,'marginType':ex.margin,'crossLeverage':ex.leverage},
                    'referencePrice':'2500','exitFeeRate':'0.0008','maximumPermittedLeverage':'100'}
            engine.advance(tid,ctx)
            engine=Lifecycle(path,ex,lambda:cfg)
            for _ in range(4):
                if engine.reconcile(tid)['state']=='PROTECTED':break
            self.assertEqual(engine.get(tid)['state'],'PROTECTED')
            ex.positions=[];ex.algos[0].update(algoStatus='FILLED',actualOrderId='3')
            self.assertEqual(engine.reconcile(tid)['state'],'CLOSED')
            self.assertEqual(sum(op=='post_capi_v3_order' for op,p in ex.calls),1)
            self.assertEqual(sum(op=='post_capi_v3_placeTpSlOrder' for op,p in ex.calls),1)
    def test_complete_cycle(self):self.cycle('full')
    def test_partial_fill_cancel_and_tp(self):self.cycle('partial')
    def test_entry_timeout_restart(self):self.cycle('entry_timeout')
    def test_tp_timeout_restart(self):self.cycle('tp_timeout')
    def test_settings_readback_before_entry(self):self.cycle('setup')

if __name__=='__main__':unittest.main()
