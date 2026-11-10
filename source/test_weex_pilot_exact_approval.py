import unittest
from weex_pilot_exact_approval import exact_approval,approved
P={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG',
   'type':'MARKET','quantity':'0.002','newClientOrderId':'wxpilot_123456789'}
class Approval(unittest.TestCase):
 def test_same_object_is_approved_twice(self):
  captured=[]
  def callback(a):
   captured.append(a)
   return a==approval
  approval=exact_approval('P1',P,'2248')
  self.assertTrue(approved(callback,approval,'post_capi_v3_order',P))
  self.assertTrue(approved(callback,approval,'post_capi_v3_order',P))
  self.assertEqual(captured,[approval,approval])
 def test_reject_changed_order(self):
  approval=exact_approval('P1',P,'2248')
  self.assertFalse(approved(lambda a:True,approval,'post_capi_v3_order',{**P,'quantity':'0.001'}))
 def test_reject_wrong_operation(self):
  approval=exact_approval('P1',P,'2248')
  self.assertFalse(approved(lambda a:True,approval,'post_capi_v3_closePositions',P))
 def test_reject_notional_above_limit(self):
  with self.assertRaisesRegex(ValueError,'ABOVE_5'):
   exact_approval('P1',P,'3000')
if __name__=='__main__':unittest.main()
