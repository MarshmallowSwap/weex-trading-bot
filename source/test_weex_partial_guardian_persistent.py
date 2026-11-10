import hashlib,tempfile,unittest
from pathlib import Path
from weex_partial_guardian_persistent import register,evaluate,note_attempt
from weex_partial_exit_replace_guard import inspect
P={'id':123,'symbol':'BTCUSDT','side':'LONG','size':'0.0001'}
def a(cid,qty,typ,num):
 return dict(algoId=num,clientAlgoId=cid,symbol='BTCUSDT',positionSide='LONG',
       side='SELL',reduceOnly=True,algoStatus='UNTRIGGERED',
       quantity=qty,orderType=typ)
OTP=a('oldtp','.0002','TAKE_PROFIT_LIMIT',11)
OSL=a('oldsl','.0002','STOP_LOSS_MARKET',12)
NSL=a('newsl','.0001','STOP_LOSS_MARKET',13)
NTP=a('newtp','.0001','TAKE_PROFIT_LIMIT',14)
PARAMS={'position_id':123,'symbol':'BTCUSDT','side':'LONG','old_tp_client':'oldtp',
        'old_sl_client':'oldsl','new_tp_client':'newtp','new_sl_client':'newsl'}
class Guardian(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.db=str(Path(self.tmp.name)/'partial_guardian.sqlite')
  register(self.db,'t1',**PARAMS)
 def ev(self,algos=None,positions=None,regular_orders=None,verified=True):
  return evaluate(self.db,'t1',positions=[P] if positions is None else positions,
     algos=[OTP,OSL] if algos is None else algos,
     regular_orders=[] if regular_orders is None else regular_orders,
     authenticated_sim_readback=verified)
 def test_initial_readback_demands_new_stop(self):
  r=self.ev()
  self.assertEqual(r['state'],'NEEDS_NEW_STOP_FIRST_OFFLINE')
  self.assertFalse(r['canDispatch'])
 def test_identical_restart_binding(self):
  self.assertTrue(register(self.db,'t1',**PARAMS)['existing'])
 def test_mutating_binding_fails(self):
  with self.assertRaisesRegex(ValueError,'IMMUTABLE'):
   register(self.db,'t1',**{**PARAMS,'position_id':555})
 def test_unverified_snapshot_blocks(self):
  self.assertEqual(self.ev(verified=False)['reason'],'NO_TRUSTED_SIM_READBACK')
 def test_duplicate_snapshot_blocks(self):
  self.assertEqual(self.ev(positions=[P,P])['reason'],'POSITION_NOT_UNIQUELY_PRESENT')
 def test_missing_position_blocks(self):
  self.assertEqual(self.ev(positions=[])['reason'],'POSITION_NOT_UNIQUELY_PRESENT')
 def test_active_order_blocks(self):
  self.assertEqual(self.ev(regular_orders=[{'symbol':'BTCUSDT'}])['reason'],
                   'ACTIVE_REGULAR_ORDER_REQUIRES_RECONCILIATION')
 def test_outstanding_write_never_retried(self):
  self.ev()
  step='PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK'
  r=note_attempt(self.db,'t1',step=step,request_fingerprint='a'*64)
  self.assertFalse(r['canDispatch'])
  self.assertEqual(self.ev()['reason'],'PREVIOUS_ATTEMPT_NOT_RESOLVED')
  with self.assertRaisesRegex(ValueError,'PENDING_OUTCOME'):
   note_attempt(self.db,'t1',step=step,request_fingerprint='a'*64)
 def test_crash_restart_after_write_attempt_stays_locked(self):
  self.ev()
  note_attempt(self.db,'t1',step='PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK',
               request_fingerprint='b'*64)
  self.assertTrue(register(self.db,'t1',**PARAMS)['existing'])
  self.assertEqual(self.ev()['reason'],'PREVIOUS_ATTEMPT_NOT_RESOLVED')
 def test_changed_state_after_attempt_requires_manual_review(self):
  self.ev()
  note_attempt(self.db,'t1',step='PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK',
               request_fingerprint='c'*64)
  r=self.ev(algos=[OTP,OSL,NSL])
  self.assertEqual(r['state'],'CHANGED_AFTER_PENDING_REVIEW')
  self.assertFalse(r['canRetry'])
  self.assertEqual(self.ev(algos=[OTP,OSL,NSL])['state'],'CHANGED_AFTER_PENDING_REVIEW')
 def test_step_without_proof_rejected(self):
  with self.assertRaisesRegex(ValueError,'STEP_NOT_MATCHING_READBACK'):
   note_attempt(self.db,'t1',step='PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK',
                request_fingerprint='a'*64)
 def test_nonhex_fingerprint_rejected(self):
  self.ev()
  with self.assertRaisesRegex(ValueError,'INVALID_REQUEST_FINGERPRINT'):
   note_attempt(self.db,'t1',step='PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK',
                request_fingerprint='z'*64)
 def test_externally_restored_pair_readonly_only(self):
  r=self.ev(algos=[NSL,NTP])
  self.assertEqual(r['state'],'PAIR_RESTORED_OFFLINE_ONLY')
  self.assertIsNone(r['nextInstruction'])
  self.assertFalse(r['stopCoverageCertified'])
if __name__=='__main__':unittest.main()
