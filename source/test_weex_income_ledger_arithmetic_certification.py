"""Tamper protection tests for WEEX income ledger arithmetic."""
import unittest,copy
from weex_income_ledger_arithmetic_certification_20261109 import reconcile
R=[
 {'billId':'1','time':100,'balance':'10.00000001','income':'0.50000001'},
 {'billId':'2','time':200,'balance':'9.00000001','income':'-1.00000000'},
 {'billId':'3','time':300,'balance':'12.00000001','income':'3.00000000'}]
class Accounting(unittest.TestCase):
 def test_valid_chain(self):self.assertTrue(reconcile(R)['verified'])
 def test_reordered_valid_chain(self):self.assertTrue(reconcile(list(reversed(R)))['verified'])
 def test_one_satoshi_gap_rejected(self):
  x=copy.deepcopy(R);x[1]['income']='-0.99999999'
  self.assertFalse(reconcile(x)['verified'])
 def test_duplicate_bill_rejected(self):
  x=copy.deepcopy(R);x[1]['billId']='1'
  self.assertFalse(reconcile(x)['verified'])
 def test_bad_decimal_rejected(self):
  x=copy.deepcopy(R);x[1]['balance']='nan'
  self.assertFalse(reconcile(x)['verified'])
if __name__=='__main__':unittest.main()
