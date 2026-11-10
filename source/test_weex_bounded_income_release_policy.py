import copy,json,unittest
from pathlib import Path
from live_release_gate import bounded_income_accounting_certified as verify
ROOT=Path(__file__).resolve().parent
def load(n):return json.loads((ROOT/n).read_text(encoding='utf-8'))
class BoundedIncomeAccountingRelease(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.l=load('weex_income_ledger_arithmetic_certification_20261109.json')
  cls.c=load('weex_1000_fill_income_liquidation_classification_20261109.json')
  cls.j=load('weex_fill_income_ledger_join_20261109.json')
 def runproof(self,l=None,c=None,j=None):
  return verify(l if l is not None else self.l,c if c is not None else self.c,j if j is not None else self.j)
 def test_authentic_bounded_accounting(self):
  self.assertTrue(self.runproof())
 def test_missing_first_to_last_balance_delta_fails(self):
  x=copy.deepcopy(self.l);x['balanceArithmetic']['firstToLastBalanceDeltaUSDT']='0'
  self.assertFalse(self.runproof(l=x))
 def test_ledger_balance_gap_fails(self):
  x=copy.deepcopy(self.l);x['balanceArithmetic']['gaps']=[{'missing':'1'}]
  self.assertFalse(self.runproof(l=x))
 def test_missing_fills_fails(self):
  x=copy.deepcopy(self.j);x['matchedUniqueFillToBillCount']=999
  self.assertFalse(self.runproof(j=x))
 def test_unmatched_fill_fails(self):
  x=copy.deepcopy(self.j);x['unmatchedFillCount']=1
  self.assertFalse(self.runproof(j=x))
 def test_unverified_liquidations_fails(self):
  x=copy.deepcopy(self.c);x['liquidationEventTimingExplainsClass']=False
  self.assertFalse(self.runproof(c=x))
 def test_missing_income_window_fails(self):
  x=copy.deepcopy(self.l);x['ledgerWindowComplete']=False
  self.assertFalse(self.runproof(l=x))
 def test_parent_quote_substitution_fails(self):
  x=copy.deepcopy(self.c);x['parentCumQuoteCanBeUsedAsAccountingSource']=True
  self.assertFalse(self.runproof(c=x))
 def test_unverified_first_to_last_fails(self):
  x=copy.deepcopy(self.l);x['balanceArithmetic']['verified']=False
  self.assertFalse(self.runproof(l=x))
 def test_production_write_claim_fails(self):
  x=copy.deepcopy(self.l);x['newExchangeWrites']=1
  self.assertFalse(self.runproof(l=x))
 def test_lifetime_claim_rejected(self):
  x=copy.deepcopy(self.l);x['entireAccountLifetimeCertified']=True
  self.assertFalse(self.runproof(l=x))
if __name__=='__main__':unittest.main()
