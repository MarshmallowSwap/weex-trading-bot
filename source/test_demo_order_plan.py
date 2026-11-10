import unittest
from demo_order_plan import plan
class Test(unittest.TestCase):
 def test_long(self):self.assertTrue(plan("BTCSUSDT","LONG","0.001","x","69000","70000")["accepted"])
 def test_short(self):self.assertTrue(plan("BTCSUSDT","SHORT","0.001","x","70000","69000")["accepted"])
 def test_live_symbol(self):self.assertFalse(plan("BTCUSDT","LONG","0.001","x","69000","70000")["accepted"])
 def test_wrong_tp(self):self.assertFalse(plan("BTCSUSDT","LONG","0.001","x","70000","69000")["accepted"])
if __name__=="__main__":unittest.main()
