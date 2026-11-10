import unittest
from weex_sim_v3_guard import assess,audit
BASE='https://api-sim.weex.com'
class SimDomainTests(unittest.TestCase):
 def test_simulation_read_allowed(self):
  a=assess('GET',BASE+'/capi/v3/account/position/allPosition')
  self.assertTrue(a['allowed'])
  self.assertFalse(a['canTrade'])
 def test_production_read_denied(self):
  self.assertFalse(assess('GET','https://api-contract.weex.com/capi/v3/account/balance')['allowed'])
 def test_legacy_sim_path_denied(self):
  self.assertFalse(assess('GET',BASE+'/capi/v3/sim/balance')['allowed'])
 def test_post_order_denied_even_with_proof_flags(self):
  a=assess('POST',BASE+'/capi/v3/order',
           simulation_credentials_verified=True,isolated_account_verified=True,
           exit_verified=True,conditional_pair_verified=True)
  self.assertFalse(a['allowed'])
  self.assertFalse(a['writesEnabled'])
 def test_close_positions_denied(self):
  self.assertFalse(assess('POST',BASE+'/capi/v3/closePositions')['allowed'])
 def test_tp_sl_write_denied(self):
  self.assertFalse(assess('POST',BASE+'/capi/v3/placeTpSlOrder')['allowed'])
 def test_malicious_host_denied(self):
  self.assertFalse(assess('GET',BASE+'.evil.test/capi/v3/account/balance')['allowed'])
 def test_http_denied(self):
  self.assertFalse(assess('GET','http://api-sim.weex.com/capi/v3/account/balance')['allowed'])
 def test_audit_not_certified(self):
  r=audit()
  self.assertFalse(r['closeOnlyExitCertified'])
  self.assertFalse(r['tpLimitAndStopLossCoexistenceCertified'])
if __name__=='__main__':unittest.main()
