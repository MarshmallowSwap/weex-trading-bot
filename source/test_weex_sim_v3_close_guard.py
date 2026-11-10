import unittest
from weex_sim_v3_close_guard import plan_close,verify_close_result
P={'symbol':'BTCUSDT','position_id':123,'observed_positions':[{'id':123,'symbol':'BTCUSDT','size':'0.001','side':'LONG'}],'observed_orders':[]}
class CloseTests(unittest.TestCase):
 def test_exact_id_and_symbol_bound(self):
  r=plan_close(**P)
  self.assertEqual(r['status'],'PREPARED_OFFLINE_ONLY')
  self.assertEqual(r['requestBody'],{'symbol':'BTCUSDT','positionId':123})
  self.assertFalse(r['dispatchAllowed'])
  self.assertEqual(r['networkRequests'],0)
 def test_no_positions_blocked(self):
  self.assertEqual(plan_close(**{**P,'observed_positions':[]})['status'],'BLOCKED')
 def test_wrong_symbol_blocked(self):
  self.assertEqual(plan_close(**{**P,'symbol':'ETHUSDT'})['status'],'BLOCKED')
 def test_pending_orders_blocked(self):
  self.assertIn('PENDING',plan_close(**{**P,'observed_orders':[{'symbol':'BTCUSDT'}]})['reason'])
 def test_live_domain_denied(self):
  self.assertEqual(plan_close(**{**P,'verified_sim_host':'api-contract.weex.com'})['reason'],'NOT_ISOLATED_SIMULATION')
 def test_symbol_only_close_impossible(self):
  self.assertEqual(plan_close(**{**P,'position_id':''})['status'],'BLOCKED')
 def test_prevent_close_all(self):
  self.assertEqual(plan_close(**{**P,'symbol':''})['status'],'BLOCKED')
 def test_mismatched_close_result_rejected(self):
  p=plan_close(**P)
  x=verify_close_result(p,[{'positionId':999,'success':True,'successOrderId':4}],[])
  self.assertEqual(x['state'],'REVIEW_REQUIRED')
 def test_readback_required(self):
  p=plan_close(**P)
  x=verify_close_result(p,[{'positionId':123,'success':True,'successOrderId':4}],P['observed_positions'])
  self.assertEqual(x['state'],'REVIEW_REQUIRED')
 def test_verified_close(self):
  p=plan_close(**P)
  x=verify_close_result(p,[{'positionId':123,'success':True,'successOrderId':4}],[])
  self.assertEqual(x['state'],'CLOSED_VERIFIED_BY_READBACK')
 def test_no_automatic_retry(self):
  p=plan_close(**P)
  x=verify_close_result(p,[],[])
  self.assertFalse(x['retryAllowed'])
if __name__=='__main__':unittest.main()
