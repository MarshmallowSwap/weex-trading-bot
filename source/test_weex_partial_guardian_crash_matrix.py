"""Exercise a crash immediately after EACH of the four demo replacement writes.

Uses only the in-memory transport; checks that recovery never executes
an additional write. Fresh independent SQLite database per scenario.
"""
import tempfile,unittest
from pathlib import Path
from weex_partial_guardian_persistent import register,STEPS
from weex_partial_guardian_demo_runner import MemoryOnlyDemo,start_step,recover
from test_weex_partial_guardian_replay import B,POS,OTP,OSL,NSL,NTP

class CrashMatrix(unittest.TestCase):
 def test_all_four_after_send_interruptions(self):
  for injected in range(4):
   with self.subTest(crash_after_step=injected),tempfile.TemporaryDirectory() as temp:
    db=str(Path(temp)/'journal.sqlite')
    register(db,'trade',**B)
    ex=MemoryOnlyDemo(POS,[OTP,OSL])
    details={'old_id':{'sl':12,'tp':11},'new_sl':NSL,'new_tp':NTP}
    for i in range(4):
     ex.fail_after_write=(i==injected)
     result=start_step(db,'trade',ex,details)
     if i==injected:
      self.assertEqual(result['state'],'ACK_UNCERTAIN')
      before=ex.writes
      ex.fail_after_write=False
      retried=start_step(db,'trade',ex,details)
      self.assertEqual(ex.writes,before)
      self.assertEqual(retried['writesApplied'],0)
      after=recover(db,'trade',ex,step=STEPS[i],details=details)
      self.assertTrue(after['confirmedByReadback'])
      self.assertEqual(ex.writes,before)
     else:
      self.assertTrue(result['confirmedByReadback'])
    self.assertEqual(ex.writes,4)
    self.assertEqual(len(ex.algos),2)
    self.assertEqual({x['clientAlgoId'] for x in ex.algos},{'newsl','newtp'})
 def test_fail_before_each_write_requires_escalation(self):
  for injected in range(4):
   with self.subTest(crash_before_step=injected),tempfile.TemporaryDirectory() as temp:
    db=str(Path(temp)/'journal.sqlite')
    register(db,'trade',**B)
    ex=MemoryOnlyDemo(POS,[OTP,OSL])
    details={'old_id':{'sl':12,'tp':11},'new_sl':NSL,'new_tp':NTP}
    for i in range(injected):
     self.assertTrue(start_step(db,'trade',ex,details)['confirmedByReadback'])
    ex.fail_before_write=True
    first=start_step(db,'trade',ex,details)
    self.assertEqual(first['state'],'ACK_UNCERTAIN')
    ex.fail_before_write=False
    before=ex.writes
    repeated=start_step(db,'trade',ex,details)
    self.assertEqual(repeated['writesApplied'],0)
    self.assertEqual(ex.writes,before)
    check=recover(db,'trade',ex,step=STEPS[injected],details=details)
    self.assertEqual(check['reason'],'STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
if __name__=='__main__':unittest.main()
