"""Offline checks for separate durable exact-scope exit-only policy."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_supervised_exit_policy_v7 import grant,status,consume,run_exit,ExitDenied
from weex_supervised_crash_executor_v2 import CLIENT_ID
P={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',
   'quantity':'0.001','newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
   'reduceOnly':True}
E={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
   'symbol':'ETHUSDT','quantity':'0.001','positionId':'123','stopAlgoId':'456'}
class ExitPolicyTests(unittest.TestCase):
 def authorize(self,td):
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   return grant(td,operator_authorized=True,duration=600)
 def test_grant_requires_operator_and_stopped_integrity(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ExitDenied):grant(td)
   with patch('live_control.state',return_value={'mode':'RUNNING'}),patch('live_control.build_errors',return_value=[]):
    with self.assertRaises(ExitDenied):grant(td,operator_authorized=True)
 def test_one_shot_scope_enforced_and_consumed(self):
  with tempfile.TemporaryDirectory() as td:
   self.authorize(td)
   self.assertTrue(status(td)['canClose'])
   for p,e in ((dict(P,reduceOnly=False),E),(dict(P,quantity='0.01'),E),
               (P,dict(E,stopAlgoId='')),(P,dict(E,clientOrderId='wrong'))):
    with self.subTest(p=p,e=e):self.assertFalse(consume(td,'post_capi_v3_order',p,e))
   self.assertTrue(status(td)['canClose'])
   self.assertTrue(consume(td,'post_capi_v3_order',P,E))
   self.assertFalse(consume(td,'post_capi_v3_order',P,E))
   self.assertFalse(status(td)['canClose'])
 def test_permit_never_regrants(self):
  with tempfile.TemporaryDirectory() as td:
   self.authorize(td)
   with self.assertRaises(ExitDenied):self.authorize(td)
 def test_no_grant_no_live_close(self):
  with tempfile.TemporaryDirectory() as td:
   def reject(**kw):raise AssertionError('NO_DISPATCH_WITHOUT_PERMIT')
   r=run_exit(td,sender=reject)
   self.assertEqual(r['status'],'EXIT_POLICY_NOT_AUTHORIZED')
 def test_runner_applies_exact_callback_and_single_use(self):
  with tempfile.TemporaryDirectory() as td:
   self.authorize(td)
   def fake_sender(*,root,operator_approval):
    self.assertTrue(operator_approval('post_capi_v3_order',P,E))
    return {'status':'FAKE_SIM_ACK','exchangeWrites':0}
   r=run_exit(td,sender=fake_sender)
   self.assertEqual(r['status'],'FAKE_SIM_ACK')
   self.assertFalse(r['releaseCertified'])
   self.assertEqual(run_exit(td,sender=fake_sender)['status'],'EXIT_POLICY_NOT_AUTHORIZED')
if __name__=='__main__':unittest.main()
