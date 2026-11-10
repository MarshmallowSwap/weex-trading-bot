import unittest
from live_1x_attribution_evidence import evaluate
O={"verified":True,"clientOrderId":"bot1","orderId":"o1","symbol":"ETHUSDT","positionSide":"LONG","executedQty":"1"}
P={"symbol":"ETHUSDT","side":"LONG","size":"1","id":"456"}
K=dict(before_complete=True,after_complete=True,exclusive_bot_window=True)
class T(unittest.TestCase):
 def test_candidate_not_authorized(self):
  r=evaluate([],[P],O,**K);self.assertFalse(r["verified"]);self.assertFalse(r["closingAllowed"])
 def test_existing_position(self):
  self.assertEqual(evaluate([P],[P],O,**K)["reason"],"PREEXISTING_OR_AMBIGUOUS_POSITION")
 def test_incomplete(self):
  self.assertFalse(evaluate([],[P],O,**dict(K,before_complete=False))["verified"])
 def test_mismatch(self):
  self.assertEqual(evaluate([],[dict(P,size="2")],O,**K)["reason"],"SIZE_MISMATCH")
 def test_mixed(self):
  self.assertFalse(evaluate([],[P],O,**dict(K,exclusive_bot_window=False))["verified"])
if __name__=="__main__":unittest.main()
