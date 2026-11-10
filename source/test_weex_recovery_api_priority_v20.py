"""Offline API traffic priority regression: no HTTP requests or real account writes."""
import tempfile,unittest
from pathlib import Path
from weex_api_budget import Budget,BudgetDeferred

class Priorities(unittest.TestCase):
 def budget(self,root,used=0):
  b=Budget(root,clock=lambda:1000.0)
  with b.db() as db:
   db.execute("INSERT INTO api_limits_v2 VALUES(?,?,?,?,?)",('REQUEST_WEIGHT',600,490,1000,'test'))
   db.execute("INSERT INTO api_limits_v2 VALUES(?,?,?,?,?)",('ORDERS',60,50,1000,'test'))
   if used:db.execute("INSERT INTO api_calls_v1 VALUES(?,?,?,?)",(999,used,0,'/test'))
  return b
 def test_public_market_yields_to_250_recovery_reserve(self):
  with tempfile.TemporaryDirectory() as td:
   b=self.budget(td,240)
   with self.assertRaisesRegex(BudgetDeferred,'MARKET_YIELDS_TO_RECOVERY_API_RESERVE'):
    b.reserve('GET','https://api-contract.weex.com/capi/v3/market/klines')
 def test_boundary_admits_last_low_priority_unit(self):
  with tempfile.TemporaryDirectory() as td:
   b=self.budget(td,239)
   self.assertEqual(b.reserve('GET','https://api-contract.weex.com/capi/v3/market/klines'),1)
   with self.assertRaises(BudgetDeferred):
    b.reserve('GET','https://api-contract.weex.com/capi/v3/market/depth')
 def test_account_reconciliation_get_not_rejected_by_public_reserve(self):
  with tempfile.TemporaryDirectory() as td:
   b=self.budget(td,240)
   self.assertEqual(b.reserve('GET','https://api-contract.weex.com/capi/v3/account/position/allPosition'),10)
   self.assertEqual(b.reserve('GET','https://api-contract.weex.com/capi/v3/openAlgoOrders'),3)
   self.assertEqual(b.reserve('GET','https://api-contract.weex.com/capi/v3/userTrades'),5)
 def test_no_long_window_public_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   b=Budget(td,clock=lambda:1000.0)
   with b.db() as db:
    db.execute("INSERT INTO api_limits_v2 VALUES(?,?,?,?,?)",('REQUEST_WEIGHT',60,490,1000,'test'))
   with self.assertRaisesRegex(BudgetDeferred,'MARKET_RECOVERY_RESERVE_UNVERIFIED'):
    b.reserve('GET','https://api-contract.weex.com/capi/v3/market/depth')
 def test_never_bypass_actual_weex_limit(self):
  with tempfile.TemporaryDirectory() as td:
   b=self.budget(td,489)
   with self.assertRaises(BudgetDeferred):
    b.reserve('GET','https://api-contract.weex.com/capi/v3/account/position/allPosition')
 def test_all_public_heavy_paths_yield(self):
  with tempfile.TemporaryDirectory() as td:
   b=self.budget(td,240)
   for path in ('klines','depth','trades','premiumIndex','apiTradingSymbols'):
    with self.subTest(path=path),self.assertRaises(BudgetDeferred):
     b.reserve('GET','https://api-contract.weex.com/capi/v3/market/'+path)
if __name__=='__main__':unittest.main()
