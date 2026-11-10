import unittest,tempfile
from pathlib import Path
from demo_hedge_multiorder import apply
def o(cid,oid,qty,side="LONG"):return {"clientOrderId":cid,"orderId":oid,"symbol":"BTCSUSDT","positionSide":side,"origQty":"5","executedQty":str(qty)}
class Tests(unittest.TestCase):
 def setUp(self):self.d=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=Path(self.d.name)/"a.db"
 def tearDown(self):self.d.cleanup()
 def test_two_entries_one_exit(self):
  self.assertEqual(apply(self.db,o("a","1",2),"ENTRY",True)["positionQty"],"2")
  self.assertEqual(apply(self.db,o("b","2",3),"ENTRY",True)["positionQty"],"5")
  self.assertEqual(apply(self.db,o("c","3",4),"EXIT",True)["positionQty"],"1")
 def test_repeat(self):
  apply(self.db,o("a","1",2),"ENTRY",True)
  self.assertEqual(apply(self.db,o("a","1",2),"ENTRY",True)["delta"],"0")
 def test_hedge_sides(self):
  apply(self.db,o("a","1",2),"ENTRY",True)
  self.assertEqual(apply(self.db,o("b","2",1,"SHORT"),"ENTRY",True)["positionQty"],"1")
 def test_overclose(self):self.assertFalse(apply(self.db,o("x","1",1),"EXIT",True)["accepted"])
 def test_manual(self):self.assertFalse(apply(self.db,o("a","1",2),"ENTRY",False)["accepted"])
 def test_live(self):self.assertFalse(apply(self.db,dict(o("a","1",2),symbol="BTCUSDT"),"ENTRY",True)["accepted"])
if __name__=="__main__":unittest.main()
