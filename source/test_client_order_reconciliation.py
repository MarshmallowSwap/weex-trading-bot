import unittest,tempfile
from pathlib import Path
from execution_intent_ledger import register
from client_order_reconciliation import bind_client_id,review_fills
class Tests(unittest.TestCase):
 def test_immutable(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/"x.sqlite"
   i=register("BTCUSDT","LONG",5,"sig-1",db)
   bind_client_id(i["intentId"],"desk-sig-1",db)
   with self.assertRaises(ValueError):bind_client_id(i["intentId"],"other",db)
 def test_partial(self):
  x=review_fills("client-1",[{"clientOrderId":"client-1","origQty":"100","executedQty":"40"}])
  self.assertEqual(x["state"],"PARTIAL");self.assertEqual(x["remaining"],"60")
 def test_full(self):
  self.assertEqual(review_fills("x",[{"clientOrderId":"x","origQty":"2","executedQty":"2"}])["state"],"FILLED")
 def test_ambiguity(self):
  self.assertEqual(review_fills("x",[{"clientOrderId":"x"},{"clientOrderId":"x"}])["state"],"UNKNOWN")
 def test_invalid(self):
  self.assertEqual(review_fills("x",[{"clientOrderId":"x","origQty":"2","executedQty":"3"}])["state"],"UNKNOWN")
if __name__=="__main__":unittest.main()
