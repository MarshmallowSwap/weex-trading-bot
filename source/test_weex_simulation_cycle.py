import copy,json,socket,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import Mock,patch
import weex_simulation_cycle as cycle
from weex_simulation_settlement import validate_empirical_contract
from weex_simulation_domain import SIM,capture_request,validate_contract
from weex_margin_sizing import contract_rules
import test_weex_lifecycle as lifecycle_tests

FIXTURE=Path(__file__).parent/'simulation_domain'/'settlement_calibration.json'
if not FIXTURE.exists():FIXTURE=Path(__file__).parent.parent/'minimal_simulation_calibration.json'

class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.evidence=json.loads(FIXTURE.read_text())
        self.when=datetime.fromisoformat(self.evidence['finishedAt'])+timedelta(seconds=1)
        self.meta={'symbol':'BTCUSDT','baseAsset':'BTC','quoteAsset':'USDT','marginAsset':'USDT',
            'contractType':'PERPETUAL','forwardContractFlag':False,'quantityPrecision':4,
            'pricePrecision':1,'minOrderSize':'0.0001','maxOrderSize':'10','marketOpenLimitSize':'10',
            'contractVal':'0.0001','minLeverage':1,'maxLeverage':200}
    def validate(self):
        return validate_empirical_contract(self.meta,self.evidence,source_host=SIM,checked_at=self.when)
    def test_empirical_scope_and_metadata_unchanged(self):
        before=copy.deepcopy(self.meta);rules=self.validate()
        self.assertEqual(str(rules['maxQuantity']),'0.0001')
        self.assertFalse(rules['strategySizeValidated']);self.assertEqual(self.meta,before)
        with self.assertRaises(ValueError):contract_rules(self.meta)
    def test_no_evidence_keeps_block(self):
        with self.assertRaises(ValueError):validate_contract(self.meta,source_host=SIM)
    def test_wrong_host_or_symbol_denied(self):
        self.evidence['host']='https://api-contract.weex.com'
        with self.assertRaises(PermissionError):self.validate()
        self.evidence['host']=SIM;self.meta['symbol']='ETHUSDT'
        with self.assertRaises(ValueError):self.validate()
    def test_stale_evidence_denied(self):
        self.when+=timedelta(days=2)
        with self.assertRaises(ValueError):self.validate()
    def test_false_accounting_or_duplicate_fills_denied(self):
        for mutate in [lambda e:e['exitFills'][0].update(realizedPnl='10'),
                       lambda e:e['entryFills'][0].update(quoteQty='100'),
                       lambda e:e['positionDuring'].update(marginSize='10'),
                       lambda e:e['entryFills'].append(e['entryFills'][0]),
                       lambda e:e['exitObservation'].update(reduceOnly=False)]:
            with self.subTest(mutate=mutate):
                self.evidence=json.loads(FIXTURE.read_text());mutate(self.evidence)
                with self.assertRaises(ValueError):self.validate()
    def test_changed_limits_denied(self):
        self.meta['maxLeverage']=400
        with self.assertRaises(ValueError):self.validate()

class ParallelLifecycleTests(lifecycle_tests.LifecycleTests):
    def setUp(self):
        super().setUp()
        self.engine=cycle.SimulationCycleLifecycle(self.path,self.exchange,lambda:self.cfg)
    def test_parallel_snapshot_still_rejects_stale_and_restores_gateway(self):
        self.entry()
        with patch.object(cycle,'now',side_effect=[0,5001]):
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_TOO_SLOW'):
                self.engine.observations(self.engine.get(self.tid))
        self.assertIs(self.engine.gateway,self.exchange)

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'journal.json'
        p=patch.object(cycle.base,'FILE',self.path);p.start();self.addCleanup(p.stop)
        self.tp={'symbol':'BTCUSDT','clientAlgoId':'test-tp','planType':'TAKE_PROFIT','triggerPrice':'82000.0',
            'executePrice':'0','quantity':'0.0001','positionSide':'LONG','triggerPriceType':'MARK_PRICE',
            'reduceOnly':True,'closePosition':False}
        self.state={'records':{},'tpRequest':self.tp,'positionDuring':{'size':'0.0001'},
                    'entryObservation':{'avgPrice':'81500'},
                    'tpObservation':{'algoId':'123','clientAlgoId':'test-tp','symbol':'BTCUSDT'}}
        self.network=Mock();self.network.request.return_value.status_code=200
    def tp_call(self,host=SIM):
        return cycle.CycleSession(self.state,'TP',self.tp,self.network).request('POST',host+'/capi/v3/placeTpSlOrder',data=json.dumps(self.tp))
    def test_real_host_and_malicious_host_denied(self):
        for host in ['https://api-contract.weex.com','https://api-sim.weex.com.evil']:
            with self.assertRaises(PermissionError):self.tp_call(host)
        self.network.request.assert_not_called()
    def test_tp_must_reduce_exact_owned_size(self):
        for key,value in [('reduceOnly',False),('closePosition',True),('quantity','0.001'),
                           ('quantity','0.00001'),('planType','STOP_LOSS'),('symbol','ETHUSDT')]:
            old=self.tp[key];self.tp[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(PermissionError):self.tp_call()
            self.tp[key]=old
        self.network.request.assert_not_called()
    def test_unknown_write_durable_and_never_retried(self):
        self.network.request.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):self.tp_call()
        self.assertEqual(json.loads(self.path.read_text())['records']['TP']['state'],'DISPATCHED_RESPONSE_UNKNOWN')
        with self.assertRaises(PermissionError):self.tp_call()
        self.assertEqual(self.network.request.call_count,1)
    def test_redirect_disabled(self):
        self.network.request.return_value.status_code=302
        with self.assertRaises(PermissionError):self.tp_call()
        self.assertFalse(self.network.request.call_args.kwargs['allow_redirects'])
    def test_cancel_only_own_algo(self):
        for oid in ['456','123']:
            guard=cycle.CycleSession(self.state,'CANCEL_TP',{'query':{'orderId':oid}},self.network)
            if oid=='456':
                with self.assertRaises(PermissionError):guard.request('DELETE',SIM+'/capi/v3/algoOrder?orderId='+oid)
            else:guard.request('DELETE',SIM+'/capi/v3/algoOrder?orderId='+oid)
        self.assertEqual(self.network.request.call_count,1)
    def test_cancel_capture_and_tp_preserve_fields(self):
        result=capture_request('delete_capi_v3_algoOrder',{'query':{'orderId':'123'}})
        self.assertEqual(result['networkRequests'],0)
        self.assertEqual(capture_request('post_capi_v3_placeTpSlOrder',self.tp)['payload'],self.tp)
    def test_completed_cycle_never_reopens_on_restart(self):
        self.path.write_text(json.dumps({'host':SIM,'cycleScope':'MINIMUM_SIMULATION_TP_ACCEPTANCE_AND_CLEANUP','status':'CLOSED_VERIFIED'}))
        with patch.object(cycle,'bind',return_value=self.path.parent),patch.object(cycle,'engine_for') as factory:
            cycle.execute()
        factory.assert_not_called()
    def test_cleanup_closes_even_if_tp_lookup_fails(self):
        evidence=json.loads(FIXTURE.read_text());state=copy.deepcopy(evidence)
        state['records']={'ENTRY':evidence['records']['ENTRY']};state['tradeId']='test'
        state['status']='EXECUTING';state['tpRequest']=self.tp
        engine=Mock();engine.get.return_value={'owned':{'positionId':str(evidence['positionDuring']['id'])}}
        def send(s,kind,op,p):s['records'][kind]={'payload':p}
        def read(op,**q):
            if op.endswith('allPosition'):return [evidence['positionDuring']]
            return evidence['entryFills'] if str(q['orderId'])==str(evidence['entryObservation']['orderId']) else evidence['exitFills']
        with patch.object(cycle.base,'wait_order',side_effect=[evidence['entryObservation'],evidence['exitObservation']]), \
             patch.object(cycle,'find_tp',side_effect=[TimeoutError(),None]), \
             patch.object(cycle,'read',side_effect=read),patch.object(cycle,'send',side_effect=send) as sender, \
             patch.object(cycle.base,'inventory',return_value=([],[],[])):
            cycle.cleanup(state,engine)
        self.assertEqual(sender.call_args.args[1],'EXIT')
        self.assertEqual(state['status'],'CLOSED_VERIFIED')
        self.assertFalse(state['takeProfitAcceptancePassed'])

if __name__=='__main__':
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_DISABLED')):
        unittest.main(verbosity=2)
