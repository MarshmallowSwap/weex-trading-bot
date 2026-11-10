import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from weex_account_bot_exclusive_policy import record,POLICY
from weex_live_manual_isolation_policy import assess
class Reader:
 def __init__(self,rows):self.rows=rows
 def account(self):return self.rows
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
 def call(self,rows):
  with patch('weex_account_bot_exclusive_policy.state',return_value={'mode':'STOPPED'}):
   return record(self.root,reader=Reader(rows))
 def test_flat_account_records_intent_only(self):
  r=self.call(([],[],[]));self.assertEqual(r['state'],'POLICY_RECORDED')
  doc=json.loads((self.root/POLICY).read_text(encoding='utf-8'))
  self.assertFalse(doc['liveDispatchEnabled'])
  self.assertFalse(doc['ownershipProvenByPolicyAlone'])
 def test_idempotent(self):
  self.call(([],[],[]));self.assertEqual(self.call(([],[],[]))['state'],'POLICY_ALREADY_RECORDED')
 def test_open_position_refused(self):
  with self.assertRaises(ValueError):self.call(([{'symbol':'BTCUSDT'}],[],[]))
 def test_open_order_refused(self):
  with self.assertRaises(ValueError):self.call(([],[{'symbol':'BTCUSDT'}],[]))
 def test_open_algo_refused(self):
  with self.assertRaises(ValueError):self.call(([],[],[{'symbol':'BTCUSDT'}]))
 def test_running_mode_refused(self):
  with patch('weex_account_bot_exclusive_policy.state',return_value={'mode':'RUNNING'}):
   with self.assertRaises(PermissionError):record(self.root,reader=Reader(([],[],[])))
 def test_flat_isolation_does_not_authorize_trading(self):
  r=assess(self.root,[],[],[],margin_preference='cross')
  self.assertEqual(r['state'],'ACCOUNT_FLAT_NO_LEGACY_MANUAL_EXPOSURE')
  self.assertFalse(r['canOpenBotTrade'])
  self.assertFalse(r['physicalCollateralIsolation'])
if __name__=='__main__':unittest.main()
