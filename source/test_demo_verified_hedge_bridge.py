import unittest,tempfile,sqlite3
from pathlib import Path
from demo_intent_binding import register,uncertain,reconcile
from demo_verified_hedge_bridge import bridge
class T(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
  self.i=Path(self.t.name)/"i.db";self.h=Path(self.t.name)/"h.db"
  self.cid=register("BTCSUSDT",db=self.i)
  uncertain(self.cid,self.i)
  self.o={"clientOrderId":self.cid,"orderId":"o1","symbol":"BTCSUSDT","positionSide":"LONG","side":"BUY","origQty":"2","executedQty":"1","status":"PARTIALLY_FILLED"}
 def tearDown(self):self.t.cleanup()
 def bind(self):self.assertTrue(reconcile(self.cid,[self.o],self.i))
 def test_unbound(self):self.assertFalse(bridge([self.o],self.cid,"ENTRY",intent_db=self.i,hedge_db=self.h)["accepted"])
 def test_bound(self):
  self.bind();self.assertEqual(bridge([self.o],self.cid,"ENTRY",intent_db=self.i,hedge_db=self.h)["delta"],"1")
 def test_duplicate(self):
  self.bind();self.assertFalse(bridge([self.o,self.o],self.cid,"ENTRY",intent_db=self.i,hedge_db=self.h)["accepted"])
 def test_bad_role(self):
  self.bind();self.assertFalse(bridge([self.o],self.cid,"EXIT",intent_db=self.i,hedge_db=self.h)["accepted"])
 def test_wrong_exchange_id(self):
  self.bind();self.assertFalse(bridge([dict(self.o,orderId="different")],self.cid,"ENTRY",intent_db=self.i,hedge_db=self.h)["accepted"])
if __name__=="__main__":unittest.main()
