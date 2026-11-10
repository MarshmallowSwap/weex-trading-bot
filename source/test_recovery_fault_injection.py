"""Offline fault injection for WEEX order recovery; no network/real orders."""
import unittest,tempfile
from pathlib import Path
from execution_intent_ledger import register,mark_uncertain
from client_order_reconciliation import bind_client_id,review_fills
from order_reconciliation_readonly import reconcile
class RecoveryScenarios(unittest.TestCase):
 def test_restart_duplicate_intent(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"test.db"
   first=register("SOLUSDT","LONG",5,"persist-sig",path)
   mark_uncertain(first["intentId"],path)
   restarted=register("SOLUSDT","LONG",5,"persist-sig",path)
   self.assertEqual(first["intentId"],restarted["intentId"])
   self.assertEqual(restarted["state"],"UNKNOWN_RECONCILIATION_REQUIRED")
   self.assertFalse(restarted["canSubmitToExchange"])
 def test_partial_fill(self):
  result=review_fills("id1",[{"clientOrderId":"id1","origQty":"10","executedQty":"4"}])
  self.assertEqual(result["state"],"PARTIAL")
  self.assertEqual(result["remaining"],"6")
 def test_cancelled(self):
  self.assertEqual(reconcile({"exchangeOrderId":"3"},[{"orderId":"3","status":"CANCELLED"}])["state"],"CANCELLED")
 def test_duplicate(self):
  d=[{"clientOrderId":"id1","origQty":"10","executedQty":"10"}]*2
  self.assertEqual(review_fills("id1",d)["state"],"UNKNOWN")
 def test_missing(self):
  self.assertEqual(review_fills("missing",[])["state"],"UNKNOWN")
 def test_incomplete(self):
  self.assertEqual(review_fills("id1",[{"clientOrderId":"id1","origQty":"10"}])["state"],"UNKNOWN")
 def test_invalid_overfill(self):
  self.assertEqual(review_fills("id1",[{"clientOrderId":"id1","origQty":"10","executedQty":"11"}])["state"],"UNKNOWN")
if __name__=="__main__":unittest.main(verbosity=2)
