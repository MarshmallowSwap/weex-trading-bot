import unittest,tempfile,sqlite3
from pathlib import Path
from demo_fill_delta_ledger import apply
class Test(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.db"
 def tearDown(self):self.tmp.cleanup()
 def runfill(self,e,role,q):
  return apply(self.db,execution_id=e,client_id="bot1",symbol="BTCSUSDT",position_side="LONG",role=role,qty=q)
 def test_duplicate_restart(self):
  self.assertTrue(self.runfill("f1","ENTRY","2")["applied"])
  self.assertFalse(self.runfill("f1","ENTRY","2")["applied"])
  self.assertEqual(self.runfill("f2","EXIT","1")["remaining"],"1")
  self.assertFalse(self.runfill("f2","EXIT","1")["applied"])
 def test_overclose_rollback(self):
  self.runfill("f1","ENTRY","2")
  with self.assertRaises(ValueError):self.runfill("f2","EXIT","3")
  self.assertEqual(self.runfill("f3","EXIT","2")["remaining"],"0")
 def test_conflicting_duplicate(self):
  self.runfill("f1","ENTRY","2")
  with self.assertRaises(ValueError):self.runfill("f1","ENTRY","3")
 def test_manual_exit(self):
  with self.assertRaises(ValueError):self.runfill("f1","EXIT","1")
 def test_live_symbol(self):
  with self.assertRaises(ValueError):apply(self.db,execution_id="f1",client_id="x",symbol="BTCUSDT",position_side="LONG",role="ENTRY",qty="1")
if __name__=="__main__":unittest.main()
