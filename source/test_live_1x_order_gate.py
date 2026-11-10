import unittest
from live_1x_order_gate import assess
BASE=dict(symbol="BTCUSDT",positions=[],open_orders=[],account_mode="CROSSED",configured_leverage=1,min_notional="1",close_procedure_verified=True,reduce_only_verified=True,client_order_binding_verified=True)
class T(unittest.TestCase):
 def test_ready_snapshot(self):self.assertTrue(assess(**BASE)["preflightPassed"])
 def test_manual(self):self.assertFalse(assess(**dict(BASE,positions=[{"symbol":"BTCUSDT"}]))["preflightPassed"])
 def test_open(self):self.assertFalse(assess(**dict(BASE,open_orders=[{"symbol":"BTCUSDT"}]))["preflightPassed"])
 def test_unknown_min(self):self.assertFalse(assess(**dict(BASE,min_notional=None))["preflightPassed"])
 def test_high_leverage(self):self.assertFalse(assess(**dict(BASE,configured_leverage=20))["preflightPassed"])
 def test_unverified_exit(self):self.assertFalse(assess(**dict(BASE,reduce_only_verified=False))["preflightPassed"])
 def test_over_budget(self):self.assertFalse(assess(**dict(BASE,requested_notional="6"))["preflightPassed"])
if __name__=="__main__":unittest.main()
