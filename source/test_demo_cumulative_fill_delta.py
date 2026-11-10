import unittest
from demo_cumulative_fill_delta import delta
O={"verified":True,"orderId":"o1","total":"10","filled":"3"}
class T(unittest.TestCase):
 def test_first(self):self.assertEqual(delta(None,O)["delta"],"3")
 def test_progress(self):self.assertEqual(delta({"orderId":"o1","filled":"3"},dict(O,filled="5"))["delta"],"2")
 def test_repeated(self):self.assertFalse(delta({"orderId":"o1","filled":"3"},O)["changed"])
 def test_regression(self):self.assertFalse(delta({"orderId":"o1","filled":"4"},O)["accepted"])
 def test_order_change(self):self.assertFalse(delta({"orderId":"other","filled":"2"},O)["accepted"])
 def test_no_position_mutation(self):self.assertFalse(delta(None,O)["applyPosition"])
if __name__=="__main__":unittest.main()
