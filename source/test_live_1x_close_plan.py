import unittest
from live_1x_close_plan import plan_close
P={"symbol":"ETHUSDT","id":"123456","marginType":"CROSSED","manualOrMixed":False}
class T(unittest.TestCase):
 def test_owned(self):
  r=plan_close(P,bot_owned_position_id="123456",bot_order_reconciled=True)
  self.assertTrue(r["allowed"]);self.assertEqual(r["payload"]["positionId"],"123456")
 def test_no_identity(self):
  self.assertFalse(plan_close(P,bot_owned_position_id=None,bot_order_reconciled=True)["allowed"])
 def test_manual(self):
  self.assertFalse(plan_close(dict(P,manualOrMixed=True),bot_owned_position_id="123456",bot_order_reconciled=True)["allowed"])
 def test_no_reconciliation(self):
  self.assertFalse(plan_close(P,bot_owned_position_id="123456")["allowed"])
 def test_wrong_id(self):
  self.assertFalse(plan_close(P,bot_owned_position_id="other",bot_order_reconciled=True)["allowed"])
if __name__=="__main__":unittest.main()
