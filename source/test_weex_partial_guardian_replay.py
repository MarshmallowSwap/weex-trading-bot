"""Offline replay of all four WEEX partial TP/SL replacement stages.

This is NOT a network trading executor. Exchange snapshots are fixtures.
One durable write-attempt marker must be matched to a later readback.
"""
import hashlib,tempfile,unittest
from pathlib import Path
from weex_partial_guardian_persistent import register,evaluate,note_attempt,confirm_step,STEPS
B=dict(position_id=123,symbol='BTCUSDT',side='LONG',old_tp_client='oldtp',
       old_sl_client='oldsl',new_tp_client='newtp',new_sl_client='newsl')
POS=[dict(id=123,symbol='BTCUSDT',side='LONG',size='.0001')]
def algo(cid,qty,typ,oid):
 return dict(algoId=oid,clientAlgoId=cid,symbol='BTCUSDT',positionSide='LONG',
             side='SELL',reduceOnly=True,algoStatus='UNTRIGGERED',
             quantity=qty,orderType=typ)
OTP=algo('oldtp','.0002','TAKE_PROFIT_LIMIT',11)
OSL=algo('oldsl','.0002','STOP_LOSS_MARKET',12)
NSL=algo('newsl','.0001','STOP_LOSS_MARKET',13)
NTP=algo('newtp','.0001','TAKE_PROFIT_LIMIT',14)
STAGES=[[OTP,OSL],[OTP,OSL,NSL],[OTP,NSL],[NSL],[NSL,NTP]]

class DurableReplay(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory()
  self.addCleanup(tmp.cleanup)
  self.path=str(Path(tmp.name)/'durable.sqlite')
  register(self.path,'trade1',**B)
 def read(self,algos):
  return evaluate(self.path,'trade1',positions=POS,algos=algos,
                  regular_orders=[],authenticated_sim_readback=True)
 def confirm(self,index,algos,fingerprint=None,verified=True):
  return confirm_step(self.path,'trade1',step=STEPS[index],
       request_fingerprint=fingerprint or hashlib.sha256(str(index).encode()).hexdigest(),
       positions=POS,algos=algos,regular_orders=[],
       authenticated_sim_readback=verified)
 def attempt(self,index):
  return note_attempt(self.path,'trade1',step=STEPS[index],
      request_fingerprint=hashlib.sha256(str(index).encode()).hexdigest())
 def test_all_four_steps_survive_restart(self):
  self.assertEqual(self.read(STAGES[0])['state'],'NEEDS_NEW_STOP_FIRST_OFFLINE')
  for i in range(4):
   self.attempt(i)
   self.assertEqual(register(self.path,'trade1',**B)['state'],'WRITE_ATTEMPT_RECORDED')
   self.assertEqual(self.read(STAGES[i])['reason'],'PREVIOUS_ATTEMPT_NOT_RESOLVED')
   outcome=self.confirm(i,STAGES[i+1])
   self.assertTrue(outcome['confirmedByReadback'])
   self.assertFalse(outcome['canDispatch'])
  self.assertEqual(self.read(STAGES[4])['state'],'PAIR_RESTORED_OFFLINE_ONLY')
 def test_timeout_without_exchange_change_is_locked(self):
  self.read(STAGES[0]);self.attempt(0)
  self.assertEqual(self.confirm(0,STAGES[0])['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
  self.assertEqual(self.read(STAGES[0])['reason'],'PREVIOUS_ATTEMPT_NOT_RESOLVED')
 def test_wrong_step_fingerprint_is_rejected(self):
  self.read(STAGES[0]);self.attempt(0)
  self.assertEqual(self.confirm(0,STAGES[1],fingerprint='f'*64)['reason'],'PENDING_FINGERPRINT_MISMATCH')
 def test_missing_readback_is_rejected(self):
  self.read(STAGES[0]);self.attempt(0)
  self.assertEqual(self.confirm(0,STAGES[1],verified=False)['reason'],'NO_TRUSTED_SIM_READBACK')
 def test_cancel_earlier_than_new_sl_proof_is_rejected(self):
  self.read(STAGES[0]);self.attempt(0)
  self.assertEqual(self.confirm(0,STAGES[2])['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
 def test_duplicate_new_sl_ids_are_rejected(self):
  self.read(STAGES[0]);self.attempt(0)
  s=STAGES[1]+[NSL]
  self.assertEqual(self.confirm(0,s)['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
 def test_unknown_open_order_blocks(self):
  self.read(STAGES[0]);self.attempt(0)
  r=confirm_step(self.path,'trade1',step=STEPS[0],request_fingerprint=hashlib.sha256(b'0').hexdigest(),
       positions=POS,algos=STAGES[1],regular_orders=[{'symbol':'BTCUSDT'}],
       authenticated_sim_readback=True)
  self.assertEqual(r['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
if __name__=='__main__':unittest.main()
