import unittest
from demo_exchange_observation import observe
O={"clientOrderId":"bot1","orderId":"exchange1","symbol":"BTCSUSDT","origQty":"2","executedQty":"1","status":"PARTIALLY_FILLED"}
class Tests(unittest.TestCase):
 def test_partial(self):
  x=observe("bot1",[O],{"bot1"});self.assertTrue(x["accepted"]);self.assertFalse(x["applyToLifecycle"])
 def test_manual(self):self.assertFalse(observe("bot1",[O],set())["accepted"])
 def test_duplicate(self):self.assertFalse(observe("bot1",[O,O],{"bot1"})["accepted"])
 def test_live(self):self.assertFalse(observe("bot1",[dict(O,symbol="BTCUSDT")],{"bot1"})["accepted"])
 def test_broken_qty(self):self.assertFalse(observe("bot1",[dict(O,executedQty="3")],{"bot1"})["accepted"])
if __name__=="__main__":unittest.main()
