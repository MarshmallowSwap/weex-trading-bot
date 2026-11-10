import tempfile,unittest
from pathlib import Path
from demo_intent_binding import register,uncertain,reconcile,connect
class T(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"temp.sqlite"
 def tearDown(self):self.tmp.cleanup()
 def test_unique(self):
  a=register("BTCSUSDT",db=self.db);b=register("BTCSUSDT",db=self.db);self.assertNotEqual(a,b)
 def test_live_denied(self):
  with self.assertRaises(ValueError):register("BTCUSDT",db=self.db)
 def test_persist(self):
  i=register("BTCSUSDT",db=self.db);self.assertTrue(uncertain(i,self.db))
  self.assertTrue(reconcile(i,[{"clientOrderId":i,"orderId":"100"}],self.db))
  c=connect(self.db);self.assertEqual(c.execute("SELECT state FROM demo_intents").fetchone()[0],"ACKNOWLEDGED");c.close()
 def test_ambiguous(self):
  i=register("BTCSUSDT",db=self.db);uncertain(i,self.db)
  self.assertFalse(reconcile(i,[{"clientOrderId":i,"orderId":"1"},{"clientOrderId":i,"orderId":"2"}],self.db))
if __name__=="__main__":unittest.main()
