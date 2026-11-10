import unittest
from weex_exact_crash_trial_admission_v15 import evaluate
CAP={'taskS4UVerified':True,'supervisorHeartbeatLive':True,
 'productionIntegrityPass':True,'reduceOnlySdkPreviewPass':True,
 'apiHeadroomReady':True,'exitPermitActive':True}
FLAT={'complete':True,'positions':[],'regularOrders':[],
 'conditionalOrders':[],'trailingOrders':[]}
class AdmissionTests(unittest.TestCase):
 def test_full_empty_snapshot_and_real_ready_prereq_only(self):
  r=evaluate(CAP,FLAT,supervisor_ready_confirmed=True)
  self.assertTrue(r['admissible']);self.assertFalse(r['mayGrantPermit'])
  self.assertFalse(r['liveReleaseCertified'])
 def test_manual_ain_cross_position_blocks(self):
  snap={**FLAT,'positions':[{'symbol':'AINUSDT','id':'901'}]}
  r=evaluate(CAP,snap,supervisor_ready_confirmed=True)
  self.assertIn('SHARED_CROSS_ACCOUNT_NOT_FLAT',r['blockers'])
 def test_manual_take_profit_alone_blocks(self):
  snap={**FLAT,'conditionalOrders':[{'symbol':'AINUSDT','algoId':'902'}]}
  self.assertFalse(evaluate(CAP,snap,supervisor_ready_confirmed=True)['admissible'])
 def test_uncertified_supervisor_blocks_even_if_other_checks_pass(self):
  r=evaluate(CAP,FLAT,supervisor_ready_confirmed=False)
  self.assertIn('SUPERVISOR_NOT_READY_TO_RECOVER',r['blockers'])
 def test_missing_permission_blocks(self):
  c=dict(CAP,exitPermitActive=False)
  self.assertFalse(evaluate(c,FLAT,supervisor_ready_confirmed=True)['admissible'])
 def test_quota_blocks(self):
  c=dict(CAP,apiHeadroomReady=False)
  self.assertIn('API_HEADROOM_INSUFFICIENT',
    evaluate(c,FLAT,supervisor_ready_confirmed=True)['blockers'])
 def test_cached_snapshot_missing_blocks(self):
  self.assertFalse(evaluate(CAP,None,supervisor_ready_confirmed=True)['admissible'])
 def test_weak_account_rows_block(self):
  self.assertFalse(evaluate(CAP,{'complete':True,'positions':[]},supervisor_ready_confirmed=True)['admissible'])
if __name__=='__main__':unittest.main()
