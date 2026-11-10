import unittest
from live_sdk_fill_observer import reconcile_fills
O=[{"orderId":"o1","clientOrderId":"bot1","executedQty":"2"}]
T=[{"orderId":"o1","id":"f1","qty":"1"},{"orderId":"o1","id":"f2","qty":"1"}]
B=[{"clientOrderId":"bot1"}]
class Tests(unittest.TestCase):
 def test_two_fills(self):self.assertEqual(reconcile_fills(O,T,B)["observations"][0]["state"],"OBSERVED_MATCH")
 def test_duplicate(self):self.assertEqual(reconcile_fills(O,T+T[:1],B)["observations"][0]["state"],"FILL_MISMATCH")
 def test_missing(self):self.assertEqual(reconcile_fills(O,T[:1],B)["observations"][0]["state"],"FILL_MISMATCH")
 def test_unknown(self):self.assertEqual(reconcile_fills(O,T,[{"clientOrderId":"manual"}])["observations"][0]["state"],"UNRESOLVED_ORDER")
 def test_no_actions(self):self.assertFalse(reconcile_fills(O,T,B)["canClosePositions"])
if __name__=="__main__":unittest.main()
