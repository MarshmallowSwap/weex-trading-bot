import unittest
from live_sdk_pilot_cycle import inspect_cycle
S={"symbol":"ETHUSDT","decision":"LONG","verifiedBotClientOrderId":"c1"}
O=[{"clientOrderId":"c1","orderId":"o1","executedQty":"0.002"}]
F=[{"orderId":"o1","qty":"0.002"}]
TP={"orderSubmissionEnabled":False,"takeProfitPrice":"2500"}
class T(unittest.TestCase):
 def test_no_order(self):self.assertEqual(inspect_cycle(dict(S,verifiedBotClientOrderId=None),[],[],[])["stage"],"PREPARE_INTENT")
 def test_reconciled(self):self.assertEqual(inspect_cycle(S,[],O,F,tp_plan=TP)["stage"],"TP_PREVIEW_READY")
 def test_duplicate(self):self.assertEqual(inspect_cycle(S,[],O+O,F,tp_plan=TP)["stage"],"RECONCILIATION_REQUIRED")
 def test_wrong_fill(self):self.assertEqual(inspect_cycle(S,[],O,[{"orderId":"o1","qty":"0.003"}],tp_plan=TP)["stage"],"RECONCILIATION_REQUIRED")
 def test_manual(self):self.assertEqual(inspect_cycle(S,[{"symbol":"ETHUSDT"}],O,F,tp_plan=TP)["stage"],"BLOCKED")
if __name__=="__main__":unittest.main()
