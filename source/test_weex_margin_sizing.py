import unittest
from weex_margin_sizing import size_from_margin
class Tests(unittest.TestCase):
 def test_margin_not_notional(self):
  a=size_from_margin(margin_usdt=5,leverage=100,reference_price=2500,quantity_step=".001")
  self.assertEqual(a["notionalUSDT"],"500.0");self.assertEqual(a["initialMarginUSDT"],"5.0")
 def test_round_down(self):
  a=size_from_margin(margin_usdt=5,leverage=10,reference_price=2300,quantity_step=".001")
  self.assertLessEqual(float(a["initialMarginUSDT"]),5)
 def test_no_invalid(self):
  with self.assertRaises(ValueError):size_from_margin(margin_usdt=5,leverage=0,reference_price=2500,quantity_step=".001")
 def test_fees(self):
  a=size_from_margin(margin_usdt=5,leverage=100,reference_price=2500,quantity_step=".001",fee_reserve_usdt="0.2")
  self.assertLessEqual(float(a["initialMarginUSDT"]),4.8)
if __name__=="__main__":unittest.main()
