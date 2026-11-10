"""Network-free TP repair crash, replay, and ambiguous-ack tests."""
import tempfile
import unittest
from pathlib import Path
from weex_tp_repair_simulator import client_id, prepare, reconcile, simulate_dispatch

class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.proposal={'eligible':True,'dispatchAllowed':False,'tradeId':'fake_ltc',
                       'symbol':'LTCUSDT','positionId':'p1'}
        self.payload={'symbol':'LTCUSDT','clientAlgoId':client_id('fake_ltc','p1'),
                      'positionSide':'LONG','quantity':'1','reduceOnly':True}
    def prepare(self):
        return prepare(self.root,self.proposal,self.payload)
    def test_durable_unknown_before_network(self):
        self.assertEqual(self.prepare()['state'],'UNKNOWN')
        self.assertTrue((self.root/'weex_tp_repair_simulation.sqlite3').exists())
    def test_restart_does_not_retry(self):
        self.prepare()
        self.assertEqual(self.prepare()['state'],'UNKNOWN')
    def test_incomplete_snapshot_stays_unknown(self):
        self.prepare()
        self.assertEqual(reconcile(self.root,'fake_ltc',{'complete':False,'orders':[]})['state'],
                         'UNKNOWN_RECONCILIATION_REQUIRED')
    def test_missing_exchange_order_no_retry(self):
        self.prepare()
        self.assertEqual(reconcile(self.root,'fake_ltc',{'complete':True,'orders':[]})['state'],
                         'REVIEW_AMBIGUOUS_OR_MISSING')
        self.assertEqual(self.prepare()['state'],'UNKNOWN')
    def test_duplicate_order_blocks(self):
        self.prepare()
        a={'clientAlgoId':self.payload['clientAlgoId'],'algoId':'x1','algoStatus':'NEW'}
        self.assertEqual(reconcile(self.root,'fake_ltc',{'complete':True,'orders':[a,dict(a,algoId='x2')]})['state'],
                         'REVIEW_AMBIGUOUS_OR_MISSING')
    def test_verified_persists_after_restart(self):
        self.prepare()
        x={'clientAlgoId':self.payload['clientAlgoId'],'algoId':'x1','algoStatus':'NEW'}
        self.assertEqual(reconcile(self.root,'fake_ltc',{'complete':True,'orders':[x]})['state'],'VERIFIED_SIMULATED')
        self.assertEqual(self.prepare()['state'],'VERIFIED_SIMULATED')
    def test_not_active_is_not_protected(self):
        self.prepare()
        x={'clientAlgoId':self.payload['clientAlgoId'],'algoId':'x1','algoStatus':'FILLED'}
        self.assertEqual(reconcile(self.root,'fake_ltc',{'complete':True,'orders':[x]})['state'],'REVIEW_NOT_ACTIVE')
    def test_payload_mutation_blocked(self):
        self.prepare()
        with self.assertRaises(ValueError):
            prepare(self.root,self.proposal,dict(self.payload,quantity='2'))
    def test_bad_permission_flag_blocks(self):
        with self.assertRaises(ValueError):
            prepare(self.root,dict(self.proposal,dispatchAllowed=True),self.payload)
    def test_retry_attempt_not_supported(self):
        with self.assertRaises(ValueError):
            client_id('fake_ltc','p1',attempt=2)
    def test_fake_transport_exactly_once(self):
        self.prepare()
        sent=[]
        first=simulate_dispatch(self.root,'fake_ltc',lambda payload:sent.append(payload))
        second=simulate_dispatch(self.root,'fake_ltc',lambda payload:sent.append(payload))
        self.assertEqual(first['state'],'SIMULATED_RESPONSE_RECEIVED_RECONCILE_REQUIRED')
        self.assertEqual(second['state'],'RECONCILE_NO_RETRY')
        self.assertEqual(len(sent),1)
    def test_fake_transport_timeout_no_resend(self):
        self.prepare()
        calls=[]
        def timeout(payload):
            calls.append(payload)
            raise TimeoutError('simulated disconnect')
        self.assertEqual(simulate_dispatch(self.root,'fake_ltc',timeout)['state'],'SIMULATED_RESPONSE_UNKNOWN')
        self.assertEqual(simulate_dispatch(self.root,'fake_ltc',timeout)['state'],'RECONCILE_NO_RETRY')
        self.assertEqual(len(calls),1)
    def test_inconsistent_exchange_id_blocks(self):
        self.prepare()
        a={'clientAlgoId':self.payload['clientAlgoId'],'algoId':'x1','algoStatus':'NEW'}
        reconcile(self.root,'fake_ltc',{'complete':True,'orders':[a]})
        self.assertEqual(reconcile(self.root,'fake_ltc',{'complete':True,'orders':[dict(a,algoId='x2')]})['state'],
                         'REVIEW_EXCHANGE_ID_CHANGED')

if __name__=='__main__':
    unittest.main()
