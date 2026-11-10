import hashlib,tempfile,unittest,json,io
from pathlib import Path
from weex_partial_guardian_persistent import register,evaluate,note_attempt,STEPS
from weex_partial_guardian_sim_readback import guardian_confirm_pending,SnapshotFailure
from test_weex_partial_guardian_replay import B,POS,OTP,OSL,NSL
class Response:
 def __init__(self,rows):self.status=200;self._content=io.BytesIO(json.dumps(rows).encode())
 def __enter__(self):return self
 def __exit__(self,*x):pass
 def read(self,n=-1):return self._content.read(n)
class Transport:
 def __init__(self,algos):self.algos=algos;self.calls=0
 def __call__(self,req,timeout):
  self.calls+=1
  path=req.full_url.split('.com',1)[-1]
  assert req.get_method()=='GET'
  if path.endswith('allPosition'):return Response(POS)
  if path.endswith('openAlgoOrders'):return Response(self.algos)
  if path.endswith('openOrders'):return Response([])
  raise AssertionError('unexpected path')
class TestPendingRealGetBridge(unittest.TestCase):
 def setUp(self):
  td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
  self.db=str(Path(td.name)/'persist.sqlite')
  self.cred=Path(td.name)/'dummy.json'
  self.cred.write_text(json.dumps({'environment':'WEEX_SIM_V3','api_key':'DUMMY',
       'secret_key':'DUMMY','passphrase':'DUMMY'}))
  register(self.db,'trade',**B)
  evaluate(self.db,'trade',positions=POS,algos=[OTP,OSL],
           regular_orders=[],authenticated_sim_readback=True)
  self.fpr=hashlib.sha256(b'legitimate').hexdigest()
  note_attempt(self.db,'trade',step=STEPS[0],request_fingerprint=self.fpr)
 def test_after_send_get_only_confirms(self):
  t=Transport([OTP,OSL,NSL])
  x=guardian_confirm_pending(self.db,'trade',transport=t,credentials_path=self.cred)
  self.assertEqual(x['state'],'DUPLICATE_STOPS_REVIEW')
  self.assertTrue(x['confirmedByReadback'])
  self.assertEqual(t.calls,3)
 def test_before_send_get_does_not_confirm(self):
  t=Transport([OTP,OSL])
  x=guardian_confirm_pending(self.db,'trade',transport=t,credentials_path=self.cred)
  self.assertEqual(x['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
  self.assertEqual(t.calls,3)
 def test_repeated_confirmation_does_not_resend(self):
  t=Transport([OTP,OSL,NSL])
  guardian_confirm_pending(self.db,'trade',transport=t,credentials_path=self.cred)
  x=guardian_confirm_pending(self.db,'trade',transport=t,credentials_path=self.cred)
  self.assertEqual(x['reason'],'NO_PENDING_STEP')
  self.assertEqual(t.calls,3)
if __name__=='__main__':unittest.main()
