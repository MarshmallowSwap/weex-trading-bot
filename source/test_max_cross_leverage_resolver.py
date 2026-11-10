import unittest
from max_cross_leverage_resolver import choose
C={"risk":{"marginModePreference":"cross","leveragePreference":"maximum_exchange_settable_per_symbol_cross"}}
class T(unittest.TestCase):
 def test_max(self):
  x=choose(symbol="BTCUSDT",account_mode="CROSSED",exchange_settable_max=400,configured_cross_leverage=20,config=C)
  self.assertTrue(x["approved"]);self.assertEqual(x["requestedLeverage"],"400");self.assertTrue(x["needsLeverageChange"])
 def test_not_cross(self):
  self.assertFalse(choose(symbol="BTCUSDT",account_mode="ISOLATED",exchange_settable_max=400,configured_cross_leverage=20,config=C)["approved"])
 def test_missing_max(self):
  self.assertEqual(choose(symbol="BTCUSDT",account_mode="CROSSED",exchange_settable_max=None,configured_cross_leverage=20,config=C)["reason"],"UNVERIFIED_ACCOUNT_MAX")
 def test_bad_max(self):
  self.assertFalse(choose(symbol="BTCUSDT",account_mode="CROSSED",exchange_settable_max=10,configured_cross_leverage=20,config=C)["approved"])
if __name__=="__main__":unittest.main()
