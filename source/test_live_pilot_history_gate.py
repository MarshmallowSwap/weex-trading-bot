import unittest
from live_pilot_history_gate import assess
O={"orderId":"a","clientOrderId":"manual"};T={"orderId":"a"}
class Tests(unittest.TestCase):
 def test_manual_not_owned(self):
  r=assess([T],[O],[],history_complete=True,positions_fresh=True)
  self.assertFalse(r["certified"]);self.assertEqual(r["verifiedBotOrderIds"],[])
 def test_stale(self):
  self.assertEqual(assess([T],[O],[],history_complete=True,positions_fresh=False)["reason"],"INCOMPLETE_OR_STALE")
 def test_missing(self):
  self.assertEqual(assess([{"orderId":"b"}],[O],[],history_complete=True,positions_fresh=True)["unmatchedHistoryTrades"],1)
 def test_verified_binding_not_live_cert(self):
  b=[{"orderId":"a","clientOrderId":"manual","verified":True}]
  r=assess([T],[O],b,history_complete=True,positions_fresh=True)
  self.assertEqual(r["verifiedBotOrderIds"],["a"]);self.assertFalse(r["canSubmitOrder"])
 def test_duplicate_history(self):
  self.assertEqual(assess([T],[O,O],[],history_complete=True,positions_fresh=True)["unmatchedHistoryTrades"],1)
if __name__=="__main__":unittest.main()
