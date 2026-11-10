import copy,json,socket,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import Mock,patch
import weex_simulation_technical_trigger as tech
import test_weex_lifecycle as fixtures
c=tech.c

class TechnicalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=patch.object(c.base,'FILE',Path(self.temp.name)/'journal.json');p.start();self.addCleanup(p.stop)
    def test_price_buffer_above_mark(self):
        self.assertEqual(str(tech.technical_price('80000.0','.1')),'80016.1')
        self.assertEqual(str(tech.technical_price('80000.01','.1')),'80016.2')
        for bad in ('NaN','Infinity','-1'):
            with self.assertRaises(ValueError):tech.technical_price(bad,'.1')
    def state(self):
        p={'symbol':'BTCUSDT','clientAlgoId':'test-tp','planType':'TAKE_PROFIT','triggerPrice':'80000.1',
           'executePrice':'0','quantity':'0.0001','positionSide':'LONG','triggerPriceType':'MARK_PRICE',
           'reduceOnly':True,'closePosition':False}
        return {'records':{},'cycleScope':tech.SCOPE,'tpRequest':p,'positionDuring':{'size':'0.0001'},
          'entryObservation':{'avgPrice':'80100'},'technicalTriggerPolicy':'MARK_PLUS_ONE_TICK',
          'technicalMarkSnapshot':{'price':'80000','symbol':'BTCUSDT','sourceHost':c.SIM,
              'observedAt':datetime.now(timezone.utc).isoformat()}}
    def call(self,state,network):
        p=state['tpRequest']
        return c.CycleSession(state,'TP',p,network).request('POST',c.SIM+'/capi/v3/placeTpSlOrder',data=json.dumps(p))
    def test_only_explicit_technical_scope_accepts_below_entry_tp(self):
        network=Mock();network.request.return_value.status_code=200
        state=self.state();state['cycleScope']='MINIMUM_SIMULATION_TP_ACCEPTANCE_AND_CLEANUP'
        with self.assertRaises(PermissionError):self.call(state,network)
        network.request.assert_not_called()
        state['cycleScope']=tech.SCOPE;self.call(state,network)
        self.assertEqual(network.request.call_count,1)
    def test_mark_provenance_freshness_and_exact_trigger_required(self):
        for mutate in [lambda s:s['technicalMarkSnapshot'].update(sourceHost='https://api-contract.weex.com'),
             lambda s:s['technicalMarkSnapshot'].update(observedAt=(datetime.now(timezone.utc)-timedelta(seconds=40)).isoformat()),
             lambda s:s['tpRequest'].update(triggerPrice='80001'),
             lambda s:s['tpRequest'].update(reduceOnly=False)]:
            state=self.state();mutate(state);network=Mock()
            with self.assertRaises(PermissionError):self.call(state,network)
            network.request.assert_not_called()
    def test_buffer_policy_checks_exact_price(self):
        state=self.state();state['technicalTriggerPolicy']='MARK_WITH_LATENCY_BUFFER'
        state['tpRequest']['triggerPrice']='80116.2'
        network=Mock();network.request.return_value.status_code=200
        self.call(state,network)
        self.assertEqual(network.request.call_count,1)
    def test_parameter_rejection_is_returned_without_retry(self):
        from weex_common.errors import ApiBusinessError
        folder=Path(self.temp.name)
        (folder/'weex_credentials.json').write_text(json.dumps({'api_key':'DUMMYKEY','secret_key':'DUMMYSECRET','passphrase':'DUMMYPASS'}))
        state=self.state();client=Mock();config=Mock();contract=Mock(return_value=client)
        def reject(*args):
            state['records']['TP']={'state':'DISPATCHED_RESPONSE_UNKNOWN','payload':state['tpRequest']}
            raise ApiBusinessError('parameter error',status_code=400,code=-1140,
                raw_body=json.dumps({'code':-1140,'msg':'Invalid trigger DUMMYKEY'}))
        client.rest_api.execute_operation.side_effect=reject
        with patch.object(c,'ROOT',folder),patch.object(c,'sdk_types',return_value=(config,contract,{})),patch.object(c,'capture_request'):
            response=c.send(state,'TP','post_capi_v3_placeTpSlOrder',state['tpRequest'])
            again=c.send(state,'TP','post_capi_v3_placeTpSlOrder',state['tpRequest'])
        self.assertEqual(response,again);self.assertFalse(response[0]['success'])
        self.assertEqual(client.rest_api.execute_operation.call_count,1)
        self.assertNotIn('DUMMYKEY',json.dumps(state))
    def test_technical_price_keeps_economics_but_fails_new_net_tp_guard(self):
        exchange=fixtures.Exchange();exchange.state={'cycleScope':tech.SCOPE,'records':{}}
        cfg=copy.deepcopy(fixtures.CFG)
        engine=tech.TechnicalLifecycle(Path(self.temp.name)/'runtime.sqlite3',exchange,lambda:cfg)
        plan=copy.deepcopy(fixtures.PLAN)
        plan['orderPreview'].update(symbol='BTCUSDT',quantity='0.0001')
        plan['sizing'].update(priceTick='.1',notionalUSDT='.25')
        item=engine.prepare('technical-fixture',plan);tid=item['id']
        engine.send_once(tid,'ENTRY','post_capi_v3_order',item['plan']['entry'],capacity={'count':0,'symbols':[]})
        with patch.object(c,'public',return_value={'symbol':'BTCUSDT','price':'2499.0','time':1}):
            result=engine.reconcile(tid)
            self.assertEqual(result['state'],'REVIEW_REQUIRED')
            self.assertEqual(result['detail']['reason'],'PNL_TP_VALIDATION_FAILED')
        owned=engine.get(tid)['owned']
        self.assertEqual(owned['actualEntryCostUSDT'],'0.2500')
        self.assertEqual(owned['actualEntryFeesUSDT'],'0.04')
        self.assertEqual(owned['tpRequest']['triggerPrice'],'2500.6')
        # This legacy simulation deliberately does not target net profit. The
        # current lifecycle requires a verified PnL preview, so must not send it.
        self.assertEqual(engine.reconcile(tid)['state'],'REVIEW_REQUIRED')
        self.assertNotIn('TP',engine.writes(tid))
        self.assertFalse(exchange.state['profitTargetUnderTest'])

if __name__=='__main__':
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_DISABLED')):
        unittest.main(verbosity=2)
