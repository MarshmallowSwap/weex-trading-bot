import tempfile,unittest
from pathlib import Path
from live_sdk_intent_journal import reserve,mark_unknown
from live_sdk_end_to_end_audit import evaluate
class Test(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=Path(self.temp.name)/"x.db"
  self.cid=reserve("s1","ETHUSDT",self.db)["clientOrderId"];mark_unknown("s1",self.db)
 def tearDown(self):self.temp.cleanup()
 def test_missing(self):
  x=evaluate([],[],[],self.db);self.assertEqual(x["state"],"RECONCILIATION_REQUIRED")
 def test_verified(self):
  o={"orderId":"a","clientOrderId":self.cid,"symbol":"ETHUSDT","executedQty":"2"}
  t=[{"orderId":"a","id":"f1","qty":"2"}]
  x=evaluate([o],[],t,self.db);self.assertEqual(x["state"],"READ_ONLY_MATCHED");self.assertFalse(x["canSubmit"])
 def test_duplicate(self):
  o={"orderId":"a","clientOrderId":self.cid,"symbol":"ETHUSDT","executedQty":"2"}
  self.assertEqual(evaluate([o,o],[],[],self.db)["state"],"BLOCKED")
 def test_mismatch(self):
  o={"orderId":"a","clientOrderId":self.cid,"symbol":"ETHUSDT","executedQty":"2"}
  self.assertEqual(evaluate([o],[],[],self.db)["fillMismatches"],1)
 def test_empty_never_verified(self):
  import tempfile
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
   result=evaluate([],[],[],Path(d)/"empty.db")
   self.assertEqual(result["state"],"NO_BOT_ORDER_EVIDENCE")
   self.assertFalse(result["canClose"])
if __name__=="__main__":unittest.main()
