import tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import position_manager_state as state
from risk_review_readonly import review
class PositionTests(unittest.TestCase):
 def test_long_high_water(self):
  with tempfile.TemporaryDirectory() as d:
   orig=state.DB;state.DB=Path(d)/"state.sqlite3"
   try:
    state.observe("TESTUSDT","LONG","2","100")
    state.observe("TESTUSDT","LONG","2","105")
    out=state.observe("TESTUSDT","LONG","2","99")
    self.assertEqual(out["favorableExtreme"],"105")
   finally:state.DB=orig
 def test_short_low_water(self):
  with tempfile.TemporaryDirectory() as d:
   orig=state.DB;state.DB=Path(d)/"state.sqlite3"
   try:
    state.observe("TESTUSDT","SHORT","2","100")
    state.observe("TESTUSDT","SHORT","2","92")
    out=state.observe("TESTUSDT","SHORT","2","97")
    self.assertEqual(out["favorableExtreme"],"92")
   finally:state.DB=orig
 def test_risk_fail_closed(self):
  self.assertEqual(review({"symbol":"TEST","side":"LONG"})["status"],"INCOMPLETE")
 def test_invalid_mark(self):
  with self.assertRaises(ValueError):state.observe("TESTUSDT","LONG","1","0")
if __name__=="__main__":unittest.main()
