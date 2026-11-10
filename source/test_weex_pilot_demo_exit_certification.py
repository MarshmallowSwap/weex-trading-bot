"""Demo certification must fail closed if any exchange proof is modified."""
import copy,unittest
from unittest.mock import patch
import weex_pilot_demo_exit_certification as module
class EvidenceCertification(unittest.TestCase):
 def test_authentic_demo_evidence_certified(self):
  r=module.certify()
  self.assertTrue(r['demoProtectedEmergencyCloseCertified'])
  self.assertTrue(r['demoReduceOnlyExitCertified'])
  self.assertFalse(r['productionNewOrdersAuthorized'])
 def check_mutation(self,name,field,value):
  original=module.read
  def fake(n):
   d=original(n)
   if n==name:
    d=copy.deepcopy(d)
    d[field]=value
   return d
  with patch.object(module,'read',side_effect=fake):
   result=module.certify()
  self.assertFalse(result['demoProtectedEmergencyCloseCertified'])
  self.assertFalse(result['productionNewOrdersAuthorized'])
 def test_wrong_host_denied(self):
  self.check_mutation('weex_sim_active_stop_close_trial_20261109.json','host',
                      'https://api-contract.weex.com')
 def test_removed_stop_proof_denied(self):
  self.check_mutation('weex_sim_active_stop_close_trial_20261109.json',
                      'stopVerifiedBeforeClose',False)
 def test_missing_reduce_only_denied(self):
  self.check_mutation('weex_sim_active_stop_close_trial_20261109.json',
                      'reduceOnlyCloseVerified',False)
 def test_wrong_close_id_denied(self):
  self.check_mutation('weex_sim_active_stop_close_independent_audit_20261109.json',
                      'closeOrderId','DIFFERENT_ORDER')
 def test_missing_stop_historical_status_denied(self):
  self.check_mutation('weex_sim_active_stop_close_independent_audit_20261109.json',
                      'stopHistoricalStatuses',[])
 def test_not_flat_denied(self):
  self.check_mutation('weex_sim_active_stop_close_independent_audit_20261109.json',
                      'accountFlat',False)
 def test_simulated_production_write_denied(self):
  self.check_mutation('weex_sim_active_stop_close_trial_20261109.json',
                      'productionWrites',1)
if __name__=='__main__':unittest.main()
