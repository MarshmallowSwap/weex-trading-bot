import tempfile,unittest
from pathlib import Path
from live_sdk_intent_journal import reserve,mark_unknown
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=Path(self.t.name)/"test.db"
 def tearDown(self):self.t.cleanup()
 def test_duplicate(self):
  a=reserve("s1","ETHUSDT",self.db);b=reserve("s1","ETHUSDT",self.db)
  self.assertEqual(a["clientOrderId"],b["clientOrderId"]);self.assertFalse(b["canSend"])
 def test_unknown_no_retry(self):
  reserve("s1","ETHUSDT",self.db);self.assertTrue(mark_unknown("s1",self.db))
  self.assertEqual(reserve("s1","ETHUSDT",self.db)["state"],"SUBMISSION_UNKNOWN")
 def test_nonpilot(self):
  with self.assertRaises(ValueError):reserve("s1","BTCUSDT",self.db)
if __name__=="__main__":unittest.main()
