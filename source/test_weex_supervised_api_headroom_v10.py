"""Offline adversarial tests for supervised crash recovery API headroom.

Only temporary SQLite ledgers. Never contacts or writes to WEEX.
"""
import tempfile,unittest
from pathlib import Path
from weex_api_budget import Budget,BudgetDeferred
class Time:
 def __init__(self):self.value=100000.
 def __call__(self):return self.value
class RecoveryHeadroomTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.clock=Time()
  self.b=Budget(Path(self.tmp.name),self.clock)
  self.b.install_rate_limits([
   {'rateLimitType':'REQUEST_WEIGHT','interval':'MINUTE','intervalNum':10,'limit':500},
   {'rateLimitType':'REQUEST_WEIGHT','interval':'SECOND','intervalNum':10,'limit':500},
   {'rateLimitType':'ORDERS','interval':'MINUTE','intervalNum':1,'limit':300}])
 def tearDown(self):self.tmp.cleanup()
 def load(self,weight=0,orders=0,at=None):
  with self.b.db() as c:
   c.execute('INSERT INTO api_calls_v1 VALUES(?,?,?,?)',
      (self.clock() if at is None else at,weight,orders,'offline_test'))
 def test_490_limit_not_hardcoded_250(self):
  self.load(weight=260,at=self.clock()-60)
  self.assertTrue(self.b.require_supervised_recovery_headroom())
 def test_preflight_reserve_blocks_260(self):
  self.load(weight=260,at=self.clock()-60)
  with self.assertRaisesRegex(BudgetDeferred,'RECOVERY_API_HEADROOM_REQUIRED'):
   self.b.require_supervised_recovery_headroom(preflight_weight=100)
 def test_reserve_preserved_after_capture(self):
  self.load(weight=339,at=self.clock()-60)
  self.assertTrue(self.b.require_supervised_recovery_headroom())
  self.load(weight=2,at=self.clock()-60)
  with self.assertRaisesRegex(BudgetDeferred,'RECOVERY_API_HEADROOM_REQUIRED'):
   self.b.require_supervised_recovery_headroom()
 def test_short_window_also_enforced(self):
  self.load(weight=470)
  with self.assertRaisesRegex(BudgetDeferred,'RECOVERY_API_HEADROOM_REQUIRED'):
   self.b.require_supervised_recovery_headroom()
 def test_order_bucket_also_enforced(self):
  self.load(orders=300)
  with self.assertRaisesRegex(BudgetDeferred,'RECOVERY_API_HEADROOM_REQUIRED'):
   self.b.require_supervised_recovery_headroom()
 def test_server_counter_snapshot_not_ignored(self):
  with self.b.db() as c:
   c.execute('INSERT INTO api_counters_v2 VALUES(?,?,?,?)',
      ('REQUEST_WEIGHT',600,345,self.clock()))
  with self.assertRaisesRegex(BudgetDeferred,'RECOVERY_API_HEADROOM_REQUIRED'):
   self.b.require_supervised_recovery_headroom()
 def test_stale_limits_fail_closed(self):
  self.clock.value+=3601
  # Use temporarily fresh local metadata to force stale policy evaluation
  with self.b.db() as c:
   c.execute("UPDATE api_meta_v1 SET value=? WHERE key='rate_limits_at'",(self.clock(),))
  with self.assertRaisesRegex(BudgetDeferred,'RECOVERY_API_LIMITS_STALE'):
   self.b.require_supervised_recovery_headroom()
 def test_cooldown_fail_closed(self):
  with self.b.db() as c:c.execute("INSERT INTO api_meta_v1 VALUES('pause',?)",(self.clock()+50,))
  with self.assertRaisesRegex(BudgetDeferred,'WAIT_API_BUDGET_BEFORE_NEW_ENTRY'):
   self.b.require_supervised_recovery_headroom()
 def test_preflight_negative_or_below_min_reserve_rejected(self):
  for qty in (0,99,-1,True):
   with self.subTest(qty=qty),self.assertRaises(BudgetDeferred):
    self.b.require_supervised_recovery_headroom(recovery_weight=qty)
if __name__=='__main__':unittest.main()
