import unittest,tempfile
from pathlib import Path
from execution_intent_ledger import register
from execution_lifecycle import create,transition,timeline
from client_order_reconciliation import bind_client_id
from verified_order_state_sync import apply,validate
def record(status,filled,client="c1"):
 return [{"orderId":"e1","clientOrderId":client,"origQty":"10","executedQty":str(filled),"status":status}]
class SyncTests(unittest.TestCase):
 def test_partial_to_filled(self):
  with tempfile.TemporaryDirectory() as d:
   i=Path(d)/"i.db";l=Path(d)/"l.db"
   x=register("BTCUSDT","LONG",5,"signal",i)["intentId"];bind_client_id(x,"c1",i)
   create(l,x)
   for s in ("APPROVED","SUBMISSION_UNKNOWN","ACKNOWLEDGED"):transition(x,s,l)
   self.assertTrue(apply(x,"c1",record("PARTIALLY_FILLED",4),l,i)["applied"])
   self.assertTrue(apply(x,"c1",record("FILLED",10),l,i)["applied"])
   self.assertFalse(apply(x,"c1",record("FILLED",10),l,i)["applied"])
 def test_unbound(self):
  with tempfile.TemporaryDirectory() as d:
   i=Path(d)/"i.db";l=Path(d)/"l.db"
   x=register("BTCUSDT","LONG",5,"signal",i)["intentId"];create(l,x)
   self.assertEqual(apply(x,"c1",record("FILLED",10),l,i)["reason"],"UNBOUND_CLIENT_ID")
 def test_inconsistent(self):
  self.assertFalse(validate("c1",record("FILLED",4))["verified"])
 def test_missing(self):
  self.assertFalse(validate("c1",[])["verified"])
if __name__=="__main__":unittest.main()
