import unittest
from official_sdk_live_order_audit import audit
class Test(unittest.TestCase):
 def test_missing(self):self.assertEqual(audit([], [{"orderId":"1"}],[])["unmatchedTradeCount"],1)
 def test_duplicate(self):self.assertEqual(audit([{"orderId":"1"},{"orderId":"1"}],[],[])["duplicateOrderIds"],["1"])
 def test_manual(self):self.assertEqual(audit([{"orderId":"1","clientOrderId":"manual"}],[],[])["botBindingsMatched"],[])
 def test_binding(self):
  self.assertEqual(audit([{"orderId":"1","clientOrderId":"bot"}],[],[{"orderId":"1","clientOrderId":"bot","verified":True}])["botBindingsMatched"],["1"])
 def test_fail_closed(self):self.assertFalse(audit([],[],[])["canSubmit"])
if __name__=="__main__":unittest.main()
