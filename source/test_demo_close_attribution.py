import unittest,tempfile,sqlite3
from pathlib import Path
from demo_close_attribution import apply_close
class T(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
  self.p=Path(self.tmp.name)/"h.db"
  with sqlite3.connect(self.p) as c:c.execute("CREATE TABLE hedge(symbol TEXT,side TEXT,qty TEXT)")
 def tearDown(self):self.tmp.cleanup()
 def test_no_position(self):
  self.assertFalse(apply_close([],"x",intent_db=self.p,hedge_db=self.p)["accepted"])
 def test_shadow_not_certified(self):
  with sqlite3.connect(self.p) as c:c.execute("INSERT INTO hedge VALUES('BTCSUSDT','LONG','1')")
  self.assertEqual(apply_close([],"x",intent_db=self.p,hedge_db=self.p)["reason"],"MIXED_POSITION_OR_CLOSE_ONLY_NOT_VERIFIED")
if __name__=="__main__":unittest.main()
