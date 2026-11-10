import unittest
from decimal import Decimal
from depth_execution_estimator import estimate
BOOK={"asks":[["100","2"],["101","4"]],"bids":[["99","2"],["98","4"]]}
class EstimatorTests(unittest.TestCase):
 def test_unknown_units_fail_closed(self):
  self.assertEqual(estimate(BOOK,"LONG",5,100,"0.0008")["status"],"UNVERIFIED_UNITS")
 def test_buy_weighted_fill(self):
  r=estimate(BOOK,"LONG",1,500,"0.001",contract_multiplier=1)
  self.assertEqual(r["status"],"SCENARIO_ONLY")
  self.assertFalse(r["eligibleForTrading"])
  self.assertEqual(Decimal(r["filledNotionalUSDT"]),Decimal("500"))
  self.assertEqual(Decimal(r["entryFeeEstimateUSDT"]),Decimal("0.500"))
 def test_insufficient_depth(self):
  r=estimate(BOOK,"SHORT",2,500,"0.001",contract_multiplier=1)
  self.assertGreater(Decimal(r["unfilledNotionalUSDT"]),0)
 def test_invalid(self):
  with self.assertRaises(ValueError):estimate(BOOK,"NEITHER",5,100,"0.001")
if __name__=="__main__":unittest.main()
