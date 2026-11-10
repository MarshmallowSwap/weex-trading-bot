import unittest
from live_pilot_fill_provenance import verify
B=[{"clientOrderId":"bot1","orderId":"a1","state":"ACKNOWLEDGED"}]
O=[{"clientOrderId":"bot1","orderId":"a1","symbol":"ETHUSDT","positionSide":"LONG","executedQty":"0.002"}]
F=[{"orderId":"a1","qty":"0.002"}]
class Tests(unittest.TestCase):
 def test_match(self):
  x=verify("bot1",B,O,F);self.assertTrue(x["verified"]);self.assertFalse(x["positionCloseAuthorized"])
 def test_manual(self):self.assertFalse(verify("manual",B,O,F)["verified"])
 def test_duplicate(self):self.assertFalse(verify("bot1",B,O+O,F)["verified"])
 def test_fill_mismatch(self):self.assertFalse(verify("bot1",B,O,[{"orderId":"a1","qty":"0.003"}])["verified"])
 def test_no_fills(self):self.assertFalse(verify("bot1",B,O,[])["verified"])
if __name__=="__main__":unittest.main()
