import unittest
from residual_protection_reconcile import check
P={"symbol":"BTCUSDT","size":"2"}
class Tests(unittest.TestCase):
 def test_over(self):
  self.assertEqual(check(P,{"remainingQty":"3"},pagination_complete=True,units_verified=True)["status"],"EXCESS_PROTECTION")
 def test_under(self):
  self.assertEqual(check(P,{"remainingQty":"1"},pagination_complete=True,units_verified=True)["status"],"UNDER_PROTECTED")
 def test_equal(self):
  self.assertEqual(check(P,{"remainingQty":"2"},pagination_complete=True,units_verified=True)["status"],"MATCHED")
 def test_unverified(self):
  self.assertEqual(check(P,{"remainingQty":"2"},pagination_complete=True)["status"],"UNKNOWN")
 def test_pagination(self):
  self.assertEqual(check(P,{"remainingQty":"2"},pagination_complete=False,units_verified=True)["status"],"UNKNOWN")
 def test_bad_data(self):
  self.assertEqual(check(P,{"remainingQty":"NaN"},pagination_complete=True,units_verified=True)["status"],"UNKNOWN")
if __name__=="__main__":unittest.main()
