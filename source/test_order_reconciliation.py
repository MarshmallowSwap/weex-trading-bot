import unittest
from order_reconciliation_readonly import reconcile
class ReconcileTests(unittest.TestCase):
 def test_unbound(self):
  self.assertEqual(reconcile({"symbol":"BTCUSDT"},[])["state"],"UNBOUND_INTENT")
 def test_filled(self):
  x=reconcile({"exchangeOrderId":"abc"},[{"orderId":"abc","status":"FILLED"}])
  self.assertEqual(x["state"],"FILLED");self.assertFalse(x["executable"])
 def test_partial(self):
  self.assertEqual(reconcile({"exchangeOrderId":"abc"},[{"orderId":"abc","status":"PARTIALLY_FILLED"}])["state"],"PARTIAL")
 def test_duplicate_exchange_id(self):
  x=reconcile({"exchangeOrderId":"abc"},[{"orderId":"abc","status":"FILLED"},{"orderId":"abc","status":"FILLED"}])
  self.assertEqual(x["state"],"UNKNOWN_RECONCILIATION_REQUIRED")
 def test_missing(self):
  self.assertEqual(reconcile({"exchangeOrderId":"abc"},[])["state"],"UNKNOWN_RECONCILIATION_REQUIRED")
if __name__=="__main__":unittest.main()
