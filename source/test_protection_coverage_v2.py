import unittest
from protection_coverage_v2 import coverage

P={"symbol":"BTCUSDT","side":"LONG","size":"2"}
def a(kind,qty):
 return {"symbol":"BTCUSDT","positionSide":"LONG","side":"SELL","orderType":kind,
         "algoStatus":"UNACTIVATED","quantity":str(qty),"reduceOnly":True,"quantityUnitVerified":True}
class Test(unittest.TestCase):
 def test_separate_types(self):
  r=coverage(P,[a("TAKE_PROFIT",2),a("STOP_MARKET",1)],[],True)
  self.assertTrue(r["tpCovered"]);self.assertFalse(r["slCovered"])
 def test_both(self):
  r=coverage(P,[a("TAKE_PROFIT",2),a("STOP_MARKET",2)],[],True)
  self.assertTrue(r["tpCovered"] and r["slCovered"])
 def test_unverified(self):
  r=coverage(P,[dict(a("TAKE_PROFIT",2),quantityUnitVerified=False)],[],True)
  self.assertFalse(r["verified"])
 def test_missing_pages(self):
  self.assertFalse(coverage(P,[],[],False)["verified"])
 def test_no_orders(self):
  r=coverage(P,[],[],True)
  self.assertTrue(r["verified"]);self.assertFalse(r["tpCovered"])
 def test_close_position_zero_quantity_covers_full(self):
  order={"symbol":"BTCUSDT","side":"SELL","positionSide":"LONG","orderType":"TAKE_PROFIT_MARKET",
         "algoStatus":"UNTRIGGERED","quantity":"0","closePosition":True,"reduceOnly":True}
  r=coverage(P,[order],[],True)
  self.assertTrue(r["verified"]);self.assertTrue(r["tpCovered"]);self.assertEqual(r["totals"]["TAKE_PROFIT"],"2")
 def test_close_position_wrong_side_fails(self):
  order={"symbol":"BTCUSDT","side":"BUY","positionSide":"LONG","orderType":"TAKE_PROFIT_MARKET",
         "algoStatus":"UNTRIGGERED","quantity":"0","closePosition":True,"reduceOnly":True}
  self.assertEqual(coverage(P,[order],[],True)["reason"],"CLOSING_SIDE_MISMATCH")
 def test_close_position_conflicting_quantity_fails(self):
  order={"symbol":"BTCUSDT","side":"SELL","positionSide":"LONG","orderType":"TAKE_PROFIT_MARKET",
         "algoStatus":"UNTRIGGERED","quantity":"1","closePosition":True,"reduceOnly":True}
  self.assertEqual(coverage(P,[order],[],True)["reason"],"CLOSE_ALL_QUANTITY_CONFLICT")
if __name__=="__main__":unittest.main()
