import unittest
from crash_recovery_readonly import assess
O={"clientOrderId":"bot_1","orderId":"w1","origQty":"2","executedQty":"2","status":"FILLED"}
B=[{"intent_id":"i1","client_id":"bot_1"}]
class Test(unittest.TestCase):
 def test_good(self):self.assertTrue(assess(B,[O],True)["canResume"])
 def test_missing(self):self.assertFalse(assess(B,[],True)["canResume"])
 def test_duplicate(self):self.assertFalse(assess(B,[O,O],True)["canResume"])
 def test_incomplete(self):self.assertFalse(assess(B,[O],False)["canResume"])
 def test_empty_bindings(self):self.assertFalse(assess([],[],True)["canResume"])
 def test_bad_quantity(self):self.assertFalse(assess(B,[dict(O,executedQty="3")],True)["canResume"])
 def test_shared_exchange_id(self):
  another=dict(O,clientOrderId="bot_2")
  self.assertFalse(assess(B+[{"intent_id":"i2","client_id":"bot_2"}],[O,another],True)["canResume"])
if __name__=="__main__":unittest.main()
