import copy,unittest
from weex_supervised_reduce_only_close_plan_v4 import compose,ClosePlanBlocked
from weex_supervised_crash_executor_v2 import CLIENT_ID
class ClosePlan(unittest.TestCase):
 def setUp(self):
  self.proof={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
   'symbol':'ETHUSDT','quantity':'0.001','positionId':'77','stopAlgoId':'555'}
  self.positions=[{'id':'77','symbol':'ETHUSDT','side':'LONG','size':'0.001'}]
  self.orders=[]
  self.stops=[{'symbol':'ETHUSDT','algoId':'555','reduceOnly':True}]
  self.settings=[{'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'100'}]
 def runplan(self):
  return compose(proof=self.proof,positions=self.positions,
   regular_orders=self.orders,conditional_orders=self.stops,settings=self.settings)
 def test_exact_reduce_only_never_sends(self):
  r=self.runplan();p=r['payload']
  self.assertEqual(p['side'],'SELL')
  self.assertEqual(p['positionSide'],'LONG')
  self.assertTrue(p['reduceOnly'])
  self.assertEqual(p['type'],'MARKET')
  self.assertEqual(p['quantity'],'0.001')
  self.assertFalse(r['liveDispatchEnabled'])
  self.assertEqual(r['networkRequests'],0)
 def test_wrong_position_denied(self):
  self.positions[0]['id']='88'
  with self.assertRaises(ClosePlanBlocked):self.runplan()
 def test_position_changed_denied(self):
  self.positions[0]['size']='0.002'
  with self.assertRaises(ClosePlanBlocked):self.runplan()
 def test_extra_open_order_denied(self):
  self.orders.append({'symbol':'ETHUSDT'})
  with self.assertRaises(ClosePlanBlocked):self.runplan()
 def test_wrong_leverage_denied(self):
  self.settings[0]['crossLeverage']='50'
  with self.assertRaises(ClosePlanBlocked):self.runplan()
 def test_missing_stop_denied(self):
  self.stops.clear()
  with self.assertRaises(ClosePlanBlocked):self.runplan()
 def test_unverified_stop_denied(self):
  self.stops[0]['reduceOnly']=False
  with self.assertRaises(ClosePlanBlocked):self.runplan()
 def test_invalid_proof_denied(self):
  self.proof['status']='UNKNOWN'
  with self.assertRaises(ClosePlanBlocked):self.runplan()
if __name__=='__main__':unittest.main()
