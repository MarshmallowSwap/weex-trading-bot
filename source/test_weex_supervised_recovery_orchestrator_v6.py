"""Fail-closed independent proposal tests; all simulated, never send a network POST."""
import unittest
from unittest.mock import patch
from weex_supervised_recovery_orchestrator_v6 import prepare
from weex_supervised_crash_executor_v2 import CLIENT_ID
P={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,'symbol':'ETHUSDT',
   'quantity':'0.001','positionId':'123','stopAlgoId':'456'}
S={'fresh':True,'oneExactPosition':True,'oneExactStop':True,'noOtherOrders':True,
   'positionId':'123','stopAlgoId':'456'}
class FakeReader:
 def account(self):
  return ([{'symbol':'ETHUSDT','side':'LONG','id':'123','size':'0.001'}],[],
          [{'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','reduceOnly':True,
            'algoId':'456','quantity':'0.001'}])
 def read(self,*a,**kw):
  return [{'symbol':'ETHUSDT','marginType':'CROSS','crossLeverage':'100'}]
def call(*,proof=P,snap=S,mode='STOPPED',integrity=True,unknown=True,reader=None):
 return prepare(root='.',reader=reader or FakeReader(),proof_reader=lambda:proof,
    account_reader=lambda:snap,control_check=lambda:(mode,integrity),unknown_check=lambda:unknown)
class OrchestratorTests(unittest.TestCase):
 def test_valid_proof_creates_proposal_only(self):
  with patch('weex_supervised_recovery_orchestrator_v6.compose',return_value={
       'status':'CLOSE_PREVIEW_ONLY','networkRequests':0,'payload':{
       'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','quantity':'0.001','reduceOnly':True}}):
   r=call()
  self.assertEqual(r['status'],'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION')
  self.assertEqual(len(r['payloadSha256']),64)
  self.assertFalse(r['closeDispatchAllowed'])
  self.assertEqual(r['networkWrites'],0)
 def test_unknown_or_running_denied(self):
  for args in ({'unknown':False},{'mode':'RUNNING'},{'integrity':False}):
   with self.subTest(args=args):
    self.assertTrue(call(**args)['status'].startswith(('NO_','BLOCKED_')))
 def test_invalid_proof_and_missing_stop_denied(self):
  self.assertEqual(call(proof={})['status'],'BLOCKED_UNVERIFIED_PROTECTION')
  self.assertEqual(call(snap=dict(S,oneExactStop=False))['status'],'BLOCKED_INDEPENDENT_SNAPSHOT')
  self.assertEqual(call(snap=dict(S,positionId='999'))['status'],'BLOCKED_ID_MISMATCH')
 def test_no_network_on_read_error(self):
  class Bad:
   def account(self):raise TimeoutError('PRIVATE')
  r=call(reader=Bad())
  self.assertEqual(r['status'],'BLOCKED_READBACK_ERROR')
  self.assertNotIn('PRIVATE',str(r))
 def test_failed_preview_denied(self):
  with patch('weex_supervised_recovery_orchestrator_v6.compose',return_value={'status':'BLOCKED'}):
   r=call()
  self.assertEqual(r['status'],'BLOCKED_PREVIEW')
 def test_integrated_close_requires_distinct_operator(self):
  from weex_supervised_recovery_orchestrator_v6 import dispatch_approved_close
  r=dispatch_approved_close()
  self.assertEqual(r['status'],'BLOCKED_EXACT_OPERATOR_APPROVAL_MISSING')
  self.assertEqual(r['networkWrites'],0)
 def test_integrated_close_binds_proof_and_payload(self):
  from weex_supervised_recovery_orchestrator_v6 import dispatch_approved_close
  payload={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
           'quantity':'0.001','reduceOnly':True}
  proof=dict(P,clientOrderId=CLIENT_ID)
  calls=[]
  def sender(client_id,*,root,reader,approval):
   self.assertEqual(client_id,CLIENT_ID)
   self.assertFalse(approval('post_capi_v3_order',dict(payload,quantity='0.01'),proof))
   self.assertFalse(approval('post_capi_v3_order',payload,dict(proof,positionId='999')))
   self.assertFalse(approval('post_capi_v3_order',payload,dict(proof,clientOrderId='wrong')))
   self.assertFalse(approval('post_wrong_order',payload,proof))
   calls.append(approval('post_capi_v3_order',payload,proof))
   return {'status':'FAKE_CLOSE_ACK','networkWrites':0}
  with patch('weex_supervised_recovery_orchestrator_v6.compose',return_value={
      'status':'CLOSE_PREVIEW_ONLY','networkRequests':0,'payload':payload}):
   r=dispatch_approved_close(reader=FakeReader(),proof_reader=lambda:P,
       account_reader=lambda:S,control_check=lambda:('STOPPED',True),
       unknown_check=lambda:True,close_sender=sender,
       operator_approval=lambda op,p,pr:True)
  self.assertEqual(r['status'],'FAKE_CLOSE_ACK')
  self.assertEqual(calls,[True])
 def test_integrated_close_denies_invalid_context_before_sender(self):
  from weex_supervised_recovery_orchestrator_v6 import dispatch_approved_close
  def bad_sender(*args,**kwargs):
   raise AssertionError('UNAUTHORIZED_DISPATCH')
  r=dispatch_approved_close(reader=FakeReader(),proof_reader=lambda:P,
       account_reader=lambda:S,control_check=lambda:('RUNNING',True),
       unknown_check=lambda:True,close_sender=bad_sender,
       operator_approval=lambda op,p,pr:True)
  self.assertEqual(r['status'],'BLOCKED_CONTROL_OR_INTEGRITY')
 def test_integrated_ack_not_considered_filled_without_readback(self):
  from weex_supervised_recovery_orchestrator_v6 import dispatch_approved_close
  payload={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
           'quantity':'0.001','reduceOnly':True}
  def sender(*args,**kwargs):
   return {'status':'CLOSE_ACK_READBACK_REQUIRED','closeOrderId':'123456'}
  def run_with(verifier):
   with patch('weex_supervised_recovery_orchestrator_v6.compose',return_value={
       'status':'CLOSE_PREVIEW_ONLY','networkRequests':0,'payload':payload}):
    return dispatch_approved_close(reader=FakeReader(),proof_reader=lambda:P,
        account_reader=lambda:S,control_check=lambda:('STOPPED',True),
        unknown_check=lambda:True,close_sender=sender,
        operator_approval=lambda op,p,pr:True,close_verifier=verifier)
  uncertain=run_with(lambda **kw:{'status':'ACCOUNT_NOT_FLAT','verifiedFlat':False})
  self.assertEqual(uncertain['status'],'CLOSE_UNCERTAIN_NEEDS_READBACK')
  self.assertFalse(uncertain['safeToRetryClose'])
  good=run_with(lambda **kw:{'status':'EXACT_CLOSE_AND_FLAT_VERIFIED','verifiedFlat':True})
  self.assertEqual(good['status'],'CLOSE_VERIFIED_BY_INDEPENDENT_GET')
  self.assertTrue(good['verifiedFlat'])
  self.assertFalse(good['releaseCertified'])
if __name__=='__main__':unittest.main()
