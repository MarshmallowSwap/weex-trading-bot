import unittest,tempfile
from pathlib import Path
from demo_shadow_lifecycle import apply,snapshot
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=Path(self.t.name)/"l.db"
 def tearDown(self):self.t.cleanup()
 def test_complete_cycle(self):
  self.assertEqual(apply("a","BTCSUSDT","LONG","ENTRY_FILL","0.03",self.db)["state"],"OPEN")
  self.assertEqual(apply("a","BTCSUSDT","LONG","EXIT_FILL","0.01",self.db)["state"],"PARTIAL")
  self.assertEqual(apply("a","BTCSUSDT","LONG","EXIT_FILL","0.02",self.db)["state"],"CLOSED")
 def test_restart_recovery(self):
  apply("a","BTCSUSDT","LONG","ENTRY_FILL","0.02",self.db)
  self.assertEqual(snapshot(self.db)[0][3],"0.02")
 def test_duplicate_entry_rejected(self):
  apply("a","BTCSUSDT","LONG","ENTRY_FILL","0.02",self.db)
  with self.assertRaises(ValueError):apply("a","BTCSUSDT","LONG","ENTRY_FILL","0.02",self.db)
 def test_overclose_rejected(self):
  apply("a","BTCSUSDT","LONG","ENTRY_FILL","0.02",self.db)
  with self.assertRaises(ValueError):apply("a","BTCSUSDT","LONG","EXIT_FILL","0.03",self.db)
 def test_unowned_rejected(self):
  with self.assertRaises(ValueError):apply("manual","BTCSUSDT","SHORT","EXIT_FILL","0.01",self.db)
 def test_live_symbol_rejected(self):
  with self.assertRaises(ValueError):apply("a","BTCUSDT","LONG","ENTRY_FILL","0.01",self.db)
if __name__=="__main__":unittest.main()
