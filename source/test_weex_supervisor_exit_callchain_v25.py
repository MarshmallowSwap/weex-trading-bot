"""Full Python call-chain EXIT drill: operator permit -> orchestrator ->
one-shot close adapter -> independent final readback. All fake transport and
snapshot evidence are confined to a tempfile. Never contact WEEX.
"""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_supervised_exit_policy_v7 import grant,run_exit,status
from weex_supervised_recovery_orchestrator_v6 import dispatch_approved_close
from weex_supervised_crash_executor_v2 import CLIENT_ID

PAYLOAD={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
 'type':'MARKET','quantity':'0.001',
 'newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
 'reduceOnly':True}
PROOF={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
 'symbol':'ETHUSDT','quantity':'0.001','positionId':'456','stopAlgoId':'789'}
DIGEST=hashlib.sha256(json.dumps(PAYLOAD,sort_keys=True,separators=(',',':')).encode()).hexdigest()
PROPOSAL={'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION',
 'clientOrderId':CLIENT_ID,'positionId':'456','stopAlgoId':'789',
 'payloadSha256':DIGEST,'payload':PAYLOAD}

class ExitChain(unittest.TestCase):
 def authorize(self,root):
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   grant(root,operator_authorized=True)
 def test_exit_full_chain_once_flat_readback(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.authorize(root)
   sent=[]
   def sender(client_id,*,root,reader,approval):
    self.assertEqual(client_id,CLIENT_ID)
    self.assertTrue(approval('post_capi_v3_order',PAYLOAD,PROOF))
    sent.append(client_id)
    return {'status':'CLOSE_ACK_READBACK_REQUIRED','closeOrderId':'123456'}
   def verifier(*,root,client_id,close_order_id,reader):
    self.assertEqual(close_order_id,'123456')
    return {'status':'EXACT_CLOSE_AND_FLAT_VERIFIED','verifiedFlat':True}
   def connected(*,root,operator_approval):
    return dispatch_approved_close(root,operator_approval=operator_approval,
      close_sender=sender,close_verifier=verifier)
   with patch('weex_supervised_recovery_orchestrator_v6.prepare',return_value=PROPOSAL):
    result=run_exit(root,sender=connected)
    self.assertEqual(result['status'],'CLOSE_VERIFIED_BY_INDEPENDENT_GET',result)
    self.assertTrue(result['verifiedFlat'])
    self.assertFalse(result['releaseCertified'])
    self.assertEqual(sent,[CLIENT_ID])
    again=run_exit(root,sender=connected)
    self.assertEqual(again['status'],'EXIT_POLICY_NOT_AUTHORIZED')
    self.assertEqual(sent,[CLIENT_ID])
 def test_no_live_exit_when_no_permit(self):
  with tempfile.TemporaryDirectory() as d:
   output=run_exit(d,sender=lambda **kw:1/0)
   self.assertEqual(output['status'],'EXIT_POLICY_NOT_AUTHORIZED')
 def test_readback_uncertainty_is_never_live_certified_or_retryable(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.authorize(root)
   attempts=[]
   def sender(client_id,*,root,reader,approval):
    self.assertTrue(approval('post_capi_v3_order',PAYLOAD,PROOF))
    attempts.append(client_id)
    return {'status':'CLOSE_ACK_READBACK_REQUIRED','closeOrderId':'123456'}
   def uncertain(*,root,client_id,close_order_id,reader):
    return {'status':'READBACK_UNCERTAIN','verifiedFlat':False}
   def connected(*,root,operator_approval):
    return dispatch_approved_close(root,operator_approval=operator_approval,
       close_sender=sender,close_verifier=uncertain)
   with patch('weex_supervised_recovery_orchestrator_v6.prepare',return_value=PROPOSAL):
    result=run_exit(root,sender=connected)
    self.assertEqual(result['status'],'CLOSE_UNCERTAIN_NEEDS_READBACK')
    self.assertFalse(result['verifiedFlat'])
    self.assertFalse(result['safeToRetryClose'])
    self.assertEqual(run_exit(root,sender=connected)['status'],'EXIT_POLICY_NOT_AUTHORIZED')
    self.assertEqual(len(attempts),1)
 def test_proposal_mismatched_digest_never_approves(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.authorize(root)
   proposal=dict(PROPOSAL,payloadSha256='0'*64)
   calls=[]
   def sender(client_id,*,root,reader,approval):
    calls.append('CHECK')
    self.assertFalse(approval('post_capi_v3_order',PAYLOAD,PROOF))
    return {'status':'BLOCKED','networkWrites':0}
   with patch('weex_supervised_recovery_orchestrator_v6.prepare',return_value=proposal):
    r=dispatch_approved_close(root,operator_approval=lambda op,p,pr:True,close_sender=sender)
    self.assertEqual(r['status'],'BLOCKED')
    self.assertEqual(calls,['CHECK'])
if __name__=='__main__':unittest.main()
