import tempfile,unittest
from pathlib import Path
from weex_live_minimal_pipeline import pipeline
S={"symbol":"ETHUSDT","decision":"LONG","signalId":"sig1","momentum":{"confirmed":True},"realOrderBook":{"passed":True}}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
  self.db=Path(self.tmp.name)/"p.db"
 def tearDown(self):self.tmp.cleanup()
 def test_wait(self):self.assertEqual(pipeline(dict(S,decision="WAIT"),[],[],journal_path=self.db)["stage"],"WAIT")
 def test_manual_excluded(self):
  self.assertEqual(pipeline(S,[{"symbol":"ETHUSDT"}],[],journal_path=self.db)["reason"],"EXISTING_EXPOSURE")
 def test_reservation_and_duplicate(self):
  a=pipeline(S,[],[],journal_path=self.db)
  b=pipeline(S,[],[],journal_path=self.db)
  self.assertEqual(a["stage"],"INTENT_RESERVED");self.assertEqual(b["reason"],"NO_RETRY")
  self.assertEqual(a["clientOrderId"],b["clientOrderId"])
 def test_no_real_orders(self):
  x=pipeline(S,[],[],journal_path=self.db)
  self.assertFalse(x["orderSubmitted"]);self.assertFalse(x["tpSubmitted"])
 def test_unverified_book(self):
  self.assertEqual(pipeline(dict(S,realOrderBook={"passed":False}),[],[],journal_path=self.db)["stage"],"WAIT")
if __name__=="__main__":unittest.main()
