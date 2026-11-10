"""V31 staging contract tests. Inject independent result snapshots, no network."""
import unittest
from weex_staged_crash_certification_v31 import check
C={'taskS4UVerified':True,'supervisorHeartbeatLive':True,'productionIntegrityPass':True,'reduceOnlySdkPreviewPass':True,'apiHeadroomReady':True}
A={'blockers':['SUPERVISOR_NOT_READY_TO_RECOVER','SHARED_CROSS_ACCOUNT_NOT_FLAT','EXACT_EXIT_PERMIT_NOT_AUTHORIZED']}
P={'blockers':['VERIFIED_OPERATIONAL_PROMOTION_CONTROLLER_NOT_INSTALLED','SHARED_CROSS_COLLATERAL_NOT_FLAT']}
class Contract(unittest.TestCase):
 def evaluate(self,c=None,a=None,p=None,x=None):
  return check(root='.',cap_reader=lambda r:C if c is None else c,
    trial_reader=lambda r:A if a is None else a,
    prom_reader=lambda r:P if p is None else p,
    permit_reader=lambda r:{'canClose':False} if x is None else x)
 def test_unknown_is_only_post_crash(self):
  r=self.evaluate()
  self.assertFalse(r['durableUnknownMustExistBeforeEntry'])
  self.assertIn('POST_ACK_DURABLE_UNKNOWN_REAL_WORKER_ENTRY',r['postCrashCertificationsRequired'])
 def test_cross_veto_never_ignores_manual(self):
  r=self.evaluate()
  self.assertIn('MANUAL_CROSS_EXPOSURE_PRESENT',r['preEntryBlockers'])
  self.assertFalse(r['manualPositionsExcludedFromRiskCheck'])
 def test_exit_not_auto_granted(self):
  r=self.evaluate()
  self.assertIn('SCOPED_OPERATOR_EXIT_PERMIT_NOT_GRANTED',r['preEntryBlockers'])
  self.assertFalse(r['operatorPermissionGrantedByThisTool'])
 def test_explicit_operator_permit_alone_not_enough(self):
  r=self.evaluate(x={'canClose':True})
  self.assertNotIn('SCOPED_OPERATOR_EXIT_PERMIT_NOT_GRANTED',r['preEntryBlockers'])
  self.assertIn('MANUAL_CROSS_EXPOSURE_PRESENT',r['preEntryBlockers'])
  self.assertFalse(r['liveReleaseCertified'])
 def test_fake_all_green_still_no_certification(self):
  r=self.evaluate(a={'blockers':[]},p={'blockers':[]},x={'canClose':True})
  self.assertFalse(r['liveReleaseCertified'])
  self.assertFalse(r['supervisorReady'])
  self.assertFalse(r['operatorPermissionGrantedByThisTool'])
 def test_real_api_quota_does_not_forge_ready(self):
  c=dict(C,apiHeadroomReady=False)
  r=self.evaluate(c=c)
  self.assertIn('API_HEADROOM_NOT_VERIFIED',r['preEntryBlockers'])
if __name__=='__main__':unittest.main()
