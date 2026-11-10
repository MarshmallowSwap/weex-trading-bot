import unittest
from weex_demo_evidence_acceptance_v32 import inspect,classify
class Proof(unittest.TestCase):
 def test_actual_exchange_sim_evidence(self):
  x=inspect();self.assertTrue(x['demoPass'],x)
  self.assertFalse(x['liveCrashCertified'])
  self.assertFalse(x['readyToRecover'])
 def test_missing_fields_must_not_pass(self):
  self.assertFalse(classify({})['demoPass'])
 def test_unsafe_live_host_does_not_fake_demo(self):
  self.assertFalse(classify({'host':'https://api-contract.weex.com'})['demoPass'])
 def test_real_release_always_false(self):
  self.assertFalse(classify({'liveCrashCertified':True,'productionReleaseGO':True})['productionReleaseGO'])
if __name__=='__main__':unittest.main()
