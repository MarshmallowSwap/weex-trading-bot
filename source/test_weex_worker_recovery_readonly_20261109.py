"""Adversarial read-only recovery tests; no API credentials or live orders."""
import copy,unittest
from weex_worker_recovery_readonly_20261109 import classify
T={'id':'wxentry_test123','symbol':'ETHUSDT','plan':{
 'entry':{'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
  'quantity':'0.002','newClientOrderId':'wxentry_test123'},'tpClientId':'wxtp_test123'}}
W={'ENTRY':{'operation':'post_capi_v3_order','state':'UNKNOWN','payload':T['plan']['entry']}}
O={'orderId':'123','clientOrderId':'wxentry_test123','symbol':'ETHUSDT','side':'BUY',
 'positionSide':'LONG','type':'MARKET','status':'FILLED','executedQty':'0.002'}
P={'id':'77','symbol':'ETHUSDT','side':'LONG','size':'0.002','marginType':'CROSSED'}
A={'algoId':'789','clientAlgoId':'wxtp_test123','symbol':'ETHUSDT','positionSide':'LONG',
 'side':'SELL','orderType':'TAKE_PROFIT_MARKET','algoStatus':'NEW','reduceOnly':True,
 'workingType':'MARK_PRICE','quantity':'0.002'}
class WorkerRecoveryTests(unittest.TestCase):
 def verify(self,*,t=None,w=None,o=None,p=None,a=None,complete=True):
  return classify(t if t is not None else T,w if w is not None else W,
   o if o is not None else [O],p if p is not None else [P],
   a if a is not None else [A],complete=complete)
 def test_exact_entry_and_tp(self):
  x=self.verify();self.assertEqual(x['recoveryState'],'ENTRY_AND_TP_CORROBORATED')
  self.assertFalse(x['safeToResendEntry']);self.assertFalse(x['mayChangeExchange'])
 def test_unseen_order_requires_manual(self):
  self.assertEqual(self.verify(o=[])['recoveryState'],'UNRESOLVED')
 def test_duplicate_client_id_blocked(self):
  dupe={**O,'orderId':'124'}
  self.assertEqual(self.verify(o=[O,dupe])['reason'],'DUPLICATE_CLIENT_ORDER_ID')
 def test_incomplete_pages_fail(self):
  self.assertEqual(self.verify(complete=False)['reason'],'INCOMPLETE_EXCHANGE_READBACK')
 def test_changed_side_fail(self):
  self.assertEqual(self.verify(o=[{**O,'side':'SELL'}])['reason'],'ENTRY_ORDER_NOT_CORROBORATED')
 def test_partial_fill_cannot_claim_full(self):
  self.assertEqual(self.verify(o=[{**O,'executedQty':'0.001','status':'FILLED'}])['reason'],'FILLED_QUANTITY_MISMATCH')
 def test_zero_fill_terminal(self):
  x=self.verify(o=[{**O,'executedQty':'0','status':'REJECTED'}],p=[],a=[])
  self.assertEqual(x['recoveryState'],'REJECTED_CONFIRMED')
  self.assertFalse(x['safeToResendEntry'])
 def test_missing_position_blocked(self):
  self.assertEqual(self.verify(p=[])['reason'],'OPEN_POSITION_MISSING_OR_AMBIGUOUS')
 def test_wrong_position_id_scope(self):
  self.assertEqual(self.verify(p=[{**P,'marginType':'ISOLATED'}])['reason'],'POSITION_IDENTITY_OR_SIZE_MISMATCH')
 def test_missing_tp_flags_unprotected(self):
  self.assertEqual(self.verify(a=[])['recoveryState'],'OPEN_UNPROTECTED_REVIEW')
 def test_fake_stop_not_accepted(self):
  self.assertEqual(self.verify(a=[{**A,'reduceOnly':False}])['recoveryState'],'OPEN_UNPROTECTED_REVIEW')
 def test_alternative_stop_ambiguous(self):
  self.assertEqual(self.verify(a=[A,{**A,'algoId':'999','clientAlgoId':'foreign'}])['recoveryState'],'OPEN_UNPROTECTED_REVIEW')
 def test_terminal_stop_fail(self):
  self.assertEqual(self.verify(a=[{**A,'algoStatus':'CANCELED'}])['recoveryState'],'OPEN_UNPROTECTED_REVIEW')
 def test_wrong_size_fail(self):
  self.assertEqual(self.verify(a=[{**A,'quantity':'0.001'}])['recoveryState'],'OPEN_UNPROTECTED_REVIEW')
 def test_missing_durable_attempt(self):
  self.assertEqual(self.verify(w={})['reason'],'NO_PERSISTED_ENTRY_ATTEMPT')
 def test_changed_durable_payload(self):
  self.assertEqual(self.verify(w={'ENTRY':{**W['ENTRY'],'payload':{**T['plan']['entry'],'quantity':'0.004'}}})['reason'],'DURABLE_ENTRY_PAYLOAD_NOT_EXACT')
 def test_no_mutation_all_branches(self):
  for k in (self.verify(),self.verify(o=[]),self.verify(a=[]),self.verify(complete=False)):
   self.assertIs(k['safeToResendEntry'],False)
   self.assertIs(k['mayChangeExchange'],False)
   self.assertIs(k['recoveryRequiresOperator'],True)
if __name__=='__main__':unittest.main()
