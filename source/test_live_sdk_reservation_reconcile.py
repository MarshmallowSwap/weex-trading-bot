import unittest,tempfile
from pathlib import Path
from live_sdk_intent_journal import reserve,mark_unknown
from live_sdk_reservation_reconcile import inspect
class T(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=Path(self.tmp.name)/"a.db"
  self.cid=reserve("signal","ETHUSDT",self.db)["clientOrderId"];mark_unknown("signal",self.db)
 def tearDown(self):self.tmp.cleanup()
 def test_missing(self):
  r=inspect([],[],self.db);self.assertEqual(r["items"][0]["reconciliation"],"UNRESOLVED_NOT_FOUND");self.assertFalse(r["canRetryUnknown"])
 def test_observed(self):
  r=inspect([{"clientOrderId":self.cid,"symbol":"ETHUSDT","orderId":"ex1"}],[],self.db)
  self.assertEqual(r["items"][0]["reconciliation"],"EXCHANGE_ORDER_OBSERVED");self.assertFalse(r["items"][0]["canClose"])
 def test_duplicate(self):
  o={"clientOrderId":self.cid,"symbol":"ETHUSDT","orderId":"ex1"}
  self.assertFalse(inspect([o,o],[],self.db)["safe"])
 def test_bad_data(self):self.assertFalse(inspect(None,[],self.db)["safe"])
if __name__=="__main__":unittest.main()
