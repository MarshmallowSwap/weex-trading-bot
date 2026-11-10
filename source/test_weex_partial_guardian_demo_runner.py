import tempfile,unittest
from pathlib import Path
from weex_partial_guardian_persistent import register,STEPS
from weex_partial_guardian_demo_runner import (MemoryOnlyDemo,start_step,recover,
                                                 FaultInjected)
from test_weex_partial_guardian_replay import B,POS,OTP,OSL,NSL,NTP
class Runner(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
  self.db=str(Path(t.name)/'guardian.sqlite')
  register(self.db,'t',**B)
  self.ex=MemoryOnlyDemo(POS,[OTP,OSL])
  self.details={'old_id':{'tp':11,'sl':12},'new_sl':NSL,'new_tp':NTP}
 def run_one(self):
  return start_step(self.db,'t',self.ex,self.details)
 def test_four_steps_memory_transport(self):
  states=('DUPLICATE_STOPS_REVIEW','NEW_STOP_ONLY_OLD_TP_REVIEW',
          'NEW_STOP_PRESENT_TP_MISSING','PAIR_RESTORED_OFFLINE_ONLY')
  for i in range(4):
   r=self.run_one()
   self.assertEqual(r['state'],states[i])
   self.assertTrue(r['confirmedByReadback'])
  self.assertEqual(self.ex.writes,4)
  self.assertEqual(self.run_one()['writesApplied'],0)
 def test_timeout_before_send_no_blind_retry(self):
  self.ex.fail_before_write=True
  first=self.run_one()
  self.assertEqual(first['state'],'ACK_UNCERTAIN')
  self.assertEqual(self.ex.writes,0)
  self.ex.fail_before_write=False
  retry=self.run_one()
  self.assertEqual(retry['writesApplied'],0)
  self.assertEqual(self.ex.writes,0)
  self.assertEqual(recover(self.db,'t',self.ex,step=first['step'],details=self.details)
                   ['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
 def test_timeout_after_send_recovered_without_repeat(self):
  self.ex.fail_after_write=True
  first=self.run_one()
  self.assertEqual(first['state'],'ACK_UNCERTAIN')
  self.assertEqual(self.ex.writes,1)
  self.ex.fail_after_write=False
  recovered=recover(self.db,'t',self.ex,step=first['step'],details=self.details)
  self.assertEqual(recovered['state'],'DUPLICATE_STOPS_REVIEW')
  self.assertEqual(self.ex.writes,1)
  next_result=self.run_one()
  self.assertEqual(next_result['state'],'NEW_STOP_ONLY_OLD_TP_REVIEW')
 def test_read_fail_does_not_write(self):
  self.ex.fail_read=True
  with self.assertRaises(FaultInjected):
   self.run_one()
  self.assertEqual(self.ex.writes,0)
 def test_memory_transport_only(self):
  with self.assertRaises(PermissionError):
   start_step(self.db,'t',object(),self.details)
 def test_unrecognized_extra_algo_blocks(self):
  self.ex.algos.append({**OSL,'algoId':999,'clientAlgoId':'unknown'})
  self.assertEqual(self.run_one()['writesApplied'],0)
  self.assertEqual(self.ex.writes,0)
 def test_position_id_change_blocks(self):
  self.ex.positions[0]['id']=444
  self.assertEqual(self.run_one()['writesApplied'],0)
  self.assertEqual(self.ex.writes,0)
 def test_after_send_uncertain_recovery_wrong_fingerprint(self):
  self.ex.fail_after_write=True
  first=self.run_one()
  changed={**self.details,'old_id':{'tp':11,'sl':88}}
  self.assertEqual(recover(self.db,'t',self.ex,step=first['step'],details=changed)
                   ['reason'],'PENDING_FINGERPRINT_MISMATCH')
  self.assertEqual(self.ex.writes,1)
if __name__=='__main__':unittest.main()
