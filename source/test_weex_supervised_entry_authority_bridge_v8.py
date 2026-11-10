"""Tests for the independent entry authority bridge: NEVER perform POST."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_supervised_entry_authority_bridge_v8 import ready,independent_evidence,external_approval,BridgeBlocked
from weex_supervised_crash_executor_v2 import CLIENT_ID
P={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET','quantity':'0.001',
   'newClientOrderId':CLIENT_ID,'slTriggerPrice':'1995','SlWorkingType':'MARK_PRICE'}
CTX={'referencePrice':'2000'}
S=[{'symbol':'ETHUSDT','marginType':'CROSS','crossLeverage':'100'}]
class BridgeTests(unittest.TestCase):
 def test_no_supervisor_no_entry(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertEqual(ready(td,supervisor_check=lambda root:False)['reason'],'INDEPENDENT_SUPERVISOR_NOT_READY')
   with self.assertRaises(BridgeBlocked):
    independent_evidence(P,CTX,root=td,supervisor_check=lambda root:False,
                         exit_status=lambda root:{'canClose':True})
 def test_no_exit_grant_no_entry(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertEqual(ready(td,supervisor_check=lambda root:True,
                          exit_status=lambda root:{'canClose':False})['reason'],
                    'EXACT_EXIT_AUTHORIZATION_MISSING')
 def test_second_account_readback_is_mandatory(self):
  with tempfile.TemporaryDirectory() as td:
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    with self.assertRaisesRegex(BridgeBlocked,'SECOND_INDEPENDENT_ACCOUNT_NOT_FLAT'):
     independent_evidence(P,CTX,root=td,
        supervisor_check=lambda root:True,exit_status=lambda root:{'canClose':True},
        read_account=lambda:([{'symbol':'ETHUSDT'}],[],[]),read_config=lambda:S)
 def test_independent_valid_proof_is_bound_to_order(self):
  with tempfile.TemporaryDirectory() as td:
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    proof=independent_evidence(P,CTX,root=td,supervisor_check=lambda root:True,
       exit_status=lambda root:{'canClose':True},
       read_account=lambda:([],[],[]),read_config=lambda:S,
       api_headroom_check=lambda:True)
   self.assertEqual(proof['clientOrderId'],CLIENT_ID)
   self.assertEqual(proof['accountFlat'],True)
   self.assertTrue(proof['nativeStopSerializationVerified'])
   self.assertTrue(proof['reduceOnlyCloseSerializationVerified'])
   self.assertFalse(proof['liveStopExistsVerified'])
   self.assertFalse(proof['liveCloseFillVerified'])
   self.assertEqual(len(proof['payloadSha256']),64)
   self.assertFalse(external_approval(dict(P,quantity='0.002'),proof,root=td))
   self.assertFalse(external_approval(P,dict(proof,payloadSha256='0'*64),root=td))
   self.assertFalse(external_approval(P,dict(proof,nativeStopSerializationVerified=False),root=td))
   self.assertFalse(external_approval(P,dict(proof,reduceOnlyCloseSerializationVerified=False),root=td))
   self.assertFalse(external_approval(P,dict(proof,observedAtMs=0),root=td))
   self.assertFalse(external_approval(P,proof,root=td))
if __name__=='__main__':unittest.main()
