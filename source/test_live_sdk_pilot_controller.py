import tempfile,unittest
from pathlib import Path
from live_sdk_pilot_controller import process
class T(unittest.TestCase):
 def test_idempotent(self):
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
   db=Path(d)/"x.db"
   a=process("test-a",db_path=db);b=process("test-a",db_path=db)
   self.assertEqual(a["clientOrderId"],b["clientOrderId"])
   self.assertEqual(b["reason"],"ALREADY_RESERVED_DO_NOT_RESUBMIT")
 def test_other_market(self):
  self.assertEqual(process("test-x","BTCUSDT")["reason"],"NOT_PILOT_SYMBOL")
 def test_never_sends(self):
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
   self.assertFalse(process("test-b",db_path=Path(d)/"x.db")["sent"])
if __name__=="__main__":unittest.main()
