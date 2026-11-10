"""Regression of bounded authenticated 1000-fill accounting, no API."""
import unittest,json
from pathlib import Path
from decimal import Decimal
from weex_1000_fill_economics_consolidated import run
class ConsolidatedAccounting(unittest.TestCase):
 def test_all_1000_fills_accounted(self):
  r=run()
  self.assertEqual(r['fillsIndividuallyVerified'],1000)
  self.assertEqual(r['fillsLinkedToOrders'],1000)
  self.assertEqual(r['ordersWithExactExchangeIdentity'],137)
  self.assertTrue(r['allOrdersFillBasedNotionalAndFeesReconciled'])
 def test_106_parent_field_conflicts_are_not_hidden(self):
  r=run()
  self.assertEqual(r['parentCumQuoteDiscrepantFilledOrders'],101)
  self.assertEqual(r['parentCumQuoteDiscrepantCanceledPartialOrders'],5)
  self.assertEqual(r['parentCumQuoteDiscrepancyTotalOrders'],106)
  self.assertEqual(r['parentCumQuoteEqualFillNotionalOrders'],31)
 def test_totals_and_scope_frozen(self):
  r=run()
  self.assertEqual(Decimal(r['executedFillNotionalUSDT']),Decimal('285334.21148003'))
  self.assertEqual(Decimal(r['executedFillFeesUSDT']),Decimal('222.70605669'))
  self.assertIs(r['fullAccountHistoryCovered'],False)
  self.assertIs(r['fundingAndNetPnLCertified'],False)
  self.assertIs(r['fullEconomicCertification'],False)
 def test_cannot_certify_live_release(self):
  r=run()
  self.assertIs(r['liveCrashRecoveryCertified'],False)
  self.assertIs(r['releaseGateOverride'],False)
  self.assertEqual(r['exchangeWrites'],0)
if __name__=='__main__':unittest.main()
