import unittest
from decimal import Decimal
from exit_order_planner import plan
P={"side":"LONG","remainingBaseQty":"5"}
KW={"break_even":"100","profit_usdt":"1","fee_rate":"0.001","tick_size":"0.01"}
class ExitTests(unittest.TestCase):
 def test_long(self):
  a=plan(P,**KW)
  self.assertEqual(a["exitSide"],"SELL")
  self.assertTrue(a["reduceOnly"])
  self.assertFalse(a["orderSubmissionEnabled"])
  self.assertGreater(Decimal(a["takeProfitPrice"]),100)
 def test_short(self):
  a=plan(dict(P,side="SHORT"),**KW)
  self.assertLess(Decimal(a["takeProfitPrice"]),100)
  self.assertEqual(a["exitSide"],"BUY")
 def test_remaining_quantity(self):
  a=plan(dict(P,remainingBaseQty="2"),**KW)
  b=plan(P,**KW)
  self.assertGreater(Decimal(a["takeProfitPrice"]),Decimal(b["takeProfitPrice"]))
 def test_trailing_long(self):
  a=plan(P,**KW,trailing_extreme="107",trailing_distance="2")
  self.assertEqual(a["stopCandidatePrice"],"105")
 def test_bad_qty(self):
  with self.assertRaises(ValueError):plan(dict(P,remainingBaseQty="0"),**KW)
if __name__=="__main__":unittest.main()
