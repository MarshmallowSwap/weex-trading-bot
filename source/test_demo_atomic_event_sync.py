import tempfile,unittest
from pathlib import Path
from demo_atomic_event_sync import sync
def o(oid,filled,side="LONG"):return {"clientOrderId":"bot1","orderId":oid,"symbol":"BTCSUSDT","positionSide":side,"origQty":"3","executedQty":str(filled)}
class T(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=Path(self.tmp.name)/"e.db"
 def tearDown(self):self.tmp.cleanup()
 def test_partial_duplicate_restart(self):
  self.assertEqual(sync(self.db,o("entry",1),role="ENTRY",owner_verified=True)["delta"],"1")
  self.assertEqual(sync(self.db,o("entry",1),role="ENTRY",owner_verified=True)["delta"],"0")
  self.assertEqual(sync(self.db,o("entry",3),role="ENTRY",owner_verified=True)["delta"],"2")
  self.assertEqual(sync(self.db,o("exit",2),role="EXIT",owner_verified=True)["delta"],"2")
 def test_unowned_exit(self):self.assertFalse(sync(self.db,o("exit",1),role="EXIT",owner_verified=True)["accepted"])
 def test_unknown_owner(self):self.assertFalse(sync(self.db,o("entry",1),role="ENTRY",owner_verified=False)["accepted"])
 def test_regression(self):
  sync(self.db,o("entry",2),role="ENTRY",owner_verified=True)
  self.assertFalse(sync(self.db,o("entry",1),role="ENTRY",owner_verified=True)["accepted"])
 def test_live_contract(self):self.assertFalse(sync(self.db,dict(o("entry",1),symbol="BTCUSDT"),role="ENTRY",owner_verified=True)["accepted"])
if __name__=="__main__":unittest.main()
