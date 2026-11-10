import unittest
from weex_simple_bot import decide
M={"decision":"LONG","momentum":{"confirmed":True},"liquidity":{"proxyOnly":False}}
C={"execution":{"enabled":False}}
class Test(unittest.TestCase):
 def test_wait(self):self.assertEqual(decide({"decision":"WAIT"},[],[],C)["decision"],"WAIT")
 def test_manual_occupied(self):
  self.assertIn("SYMBOL_OCCUPIED",decide(M,[{"symbol":"ETHUSDT"}],[],C)["reasons"])
 def test_cannot_submit(self):self.assertFalse(decide(M,[],[],C)["ordersSubmitted"])
 def test_candle_proxy_rejected(self):
  self.assertIn("REAL_ORDERBOOK_NOT_CERTIFIED",decide(dict(M,liquidity={"proxyOnly":True}),[],[],C)["reasons"])
if __name__=="__main__":unittest.main()
