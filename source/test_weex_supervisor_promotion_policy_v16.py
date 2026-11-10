import unittest,time
from weex_supervisor_promotion_policy_v16 import assess

def cap():
 return {'taskS4UVerified':True,'supervisorHeartbeatLive':True,
  'productionIntegrityPass':True,'reduceOnlySdkPreviewPass':True,
  'apiHeadroomReady':True,'exitPermitActive':True,
  'realUnknownEntryPresent':False}
def snap(now=None):
 t=time.time() if now is None else now
 return {'complete':True,'startedAtMs':int((t-1)*1000),
         'completedAtMs':int((t-.5)*1000),
         'positions':[],'regularOrders':[],
         'conditionalOrders':[],'trailingOrders':[]}
class SupervisorPromotionPolicyTests(unittest.TestCase):
 def test_never_arms_unverified_controller(self):
  r=assess(cap(),snap())
  self.assertEqual(r['state'],'PROMOTION_BLOCKED')
  self.assertIn('VERIFIED_OPERATIONAL_PROMOTION_CONTROLLER_NOT_INSTALLED',r['blockers'])
  self.assertFalse(r['heartbeatPromotionAllowed'])
  self.assertFalse(r['entryAuthorized'])
  self.assertFalse(r['closeAuthorized'])
 def test_manual_ain_position_and_tp_block_shared_cross(self):
  s=snap();s['positions']=[{'id':'901','symbol':'AINUSDT','side':'SHORT'}]
  s['conditionalOrders']=[{'algoId':'902','symbol':'AINUSDT','reduceOnly':True}]
  self.assertIn('SHARED_CROSS_COLLATERAL_NOT_FLAT',assess(cap(),s)['blockers'])
 def test_api_headroom_blocked(self):
  c=cap();c['apiHeadroomReady']=False
  self.assertIn('API_HEADROOM_NOT_SUFFICIENT',assess(c,snap())['blockers'])
 def test_exit_permit_missing(self):
  c=cap();c['exitPermitActive']=False
  self.assertIn('EXACT_EXIT_ONE_SHOT_PERMIT_ABSENT',assess(c,snap())['blockers'])
 def test_stale_account_blocks(self):
  self.assertIn('ACCOUNT_SNAPSHOT_EXPIRED',assess(cap(),snap(time.time()-40))['blockers'])
 def test_missing_snapshot_blocks(self):
  self.assertIn('FRESH_CROSS_ACCOUNT_SNAPSHOT_REQUIRED',assess(cap(),None)['blockers'])
 def test_missing_worker_unknown_does_not_create_circular_entry_condition(self):
  r=assess(cap(),snap())
  self.assertNotIn('REAL_WORKER_UNKNOWN_JOURNAL_MISSING',r['blockers'])
  self.assertTrue(r['realWorkerUnknownRequiredAfterCrash'])
 def test_untrusted_capability_flags_cannot_make_ready(self):
  c=cap();c.update(heartbeatPromotionAllowed=True,releaseCertified=True,
                  supportsExactReduceOnlyClose=True)
  r=assess(c,snap())
  self.assertFalse(r['heartbeatPromotionAllowed'])
  self.assertFalse(r['productionReleaseCertified'])
if __name__=='__main__':unittest.main()
