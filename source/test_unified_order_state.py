import tempfile,unittest
from pathlib import Path
from unified_order_state import reconcile_local
class UnifiedTests(unittest.TestCase):
 def test_unbound(self):
  with tempfile.TemporaryDirectory() as t:
   a=reconcile_local("sig","BTCUSDT","LONG",5,intent_db=Path(t)/"int.db",lifecycle_db=Path(t)/"life.db")
   self.assertTrue(a["requiresManualReconciliation"])
   self.assertEqual(a["lifecycle"],[(None,"CREATED")])
 def test_partial_and_restart(self):
  with tempfile.TemporaryDirectory() as t:
   args=dict(intent_db=Path(t)/"int.db",lifecycle_db=Path(t)/"life.db")
   orders=[{"clientOrderId":"cid","origQty":"10","executedQty":"4"}]
   a=reconcile_local("sig","BTCUSDT","LONG",5,"cid",orders,**args)
   b=reconcile_local("sig","BTCUSDT","LONG",5,"cid",orders,**args)
   self.assertEqual(a["intentId"],b["intentId"])
   self.assertEqual(a["observedFill"]["state"],"PARTIAL")
   self.assertFalse(a["exchangeWrites"])
   self.assertEqual(len(b["lifecycle"]),1)
 def test_ambiguous(self):
  with tempfile.TemporaryDirectory() as t:
   x=reconcile_local("sig","ETHUSDT","SHORT",5,"cid",[],Path(t)/"i",Path(t)/"l")
   self.assertTrue(x["requiresManualReconciliation"])
if __name__=="__main__":unittest.main()
