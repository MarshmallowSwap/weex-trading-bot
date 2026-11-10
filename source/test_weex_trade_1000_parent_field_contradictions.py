"""Regression on the five documented WEEX parent/order field contradictions."""
import json,unittest
from decimal import Decimal as D
from pathlib import Path
R=Path(__file__).resolve().parent
class ParentFieldContradictions(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.r=json.loads((R/'weex_trade_1000_parent_field_contradictions.json').read_text())
 def test_exact_five_partial_orders_reconciled(self):
  self.assertEqual(self.r['ordersExamined'],5)
  self.assertEqual(self.r['fieldContradictions'],5)
  self.assertTrue(all(x['contradictsDocumentedAverageAndCumulativeQuote'] for x in self.r['details']))
 def test_parent_total_is_not_fill_total(self):
  self.assertEqual(D(self.r['sumFillNotionalUSDT']),D('7887.7230'))
  self.assertEqual(D(self.r['sumParentCumQuoteUSDT']),D('7781.991'))
  self.assertEqual(D(self.r['sumParentMinusFillQuoteUSDT']),D('-105.7320'))
 def test_all_differences_are_mathematically_reproducible(self):
  for x in self.r['details']:
   self.assertEqual(D(x['parentQuoteUSDT'])-D(x['fillQuoteUSDT']),D(x['quoteDifferenceUSDT']))
   self.assertEqual(D(x['parentQuoteUSDT']),D(x['parentAvgPrice'])*D(x['executedQty']))
   self.assertNotEqual(D(x['parentAvgPrice']),D(x['weightedFillPrice']))
 def test_no_release_override(self):
  self.assertIs(self.r['productionReleaseAllowed'],False)
  self.assertIs(self.r['fullEconomicCertification'],False)
  self.assertEqual(self.r['exchangeWrites'],0)
if __name__=='__main__':unittest.main()
