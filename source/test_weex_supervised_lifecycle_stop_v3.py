"""Strict scoped native stop serialization in actual production Lifecycle; offline."""
import copy,tempfile,unittest,hashlib
from pathlib import Path
from test_weex_lifecycle import PLAN,CFG,Exchange
from weex_lifecycle import Lifecycle
from weex_http_guard import prepare_sdk_request

class ProductionScopedPilot(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.engine=Lifecycle(Path(self.t.name)/'worker.sqlite3',Exchange(),lambda:CFG)
  self.plan=copy.deepcopy(PLAN)
  self.plan['entrySource']='supervised_crash_pilot'
  self.plan['pilotReferencePrice']='2500'
  self.plan['requestedLeverage']='100'
  self.plan['orderPreview'].update(quantity='0.001',slTriggerPrice='2492.50',SlWorkingType='MARK_PRICE')
 def test_real_lifecycle_preserves_native_stop_exactly(self):
  from weex_supervised_crash_executor_v2 import SIGNAL_ID
  x=self.engine.prepare(SIGNAL_ID,self.plan)
  e=x['plan']['entry']
  self.assertEqual(x['id'],'wxentry_'+hashlib.sha256(SIGNAL_ID.encode()).hexdigest()[:24])
  self.assertEqual(e['slTriggerPrice'],'2492.50')
  self.assertEqual(e['SlWorkingType'],'MARK_PRICE')
  self.assertEqual(e['quantity'],'0.001')
  self.assertEqual(prepare_sdk_request('post_capi_v3_order',e)['state'],'STOPPED_BEFORE_NETWORK')
  self.assertEqual(self.engine.writes(x['id']),{})
 def test_normal_strategy_entry_has_no_attached_stop(self):
  self.plan.pop('entrySource')
  x=self.engine.prepare('regular',self.plan)
  self.assertNotIn('slTriggerPrice',x['plan']['entry'])
  self.assertNotIn('SlWorkingType',x['plan']['entry'])
 def must_block(self):
  with self.assertRaisesRegex(ValueError,'SUPERVISED_ATOMIC_STOP_SCOPE_INVALID'):
   self.engine.prepare('bad',self.plan)
 def test_pilot_rejects_50x(self):
  self.plan['requestedLeverage']='50'
  with self.assertRaisesRegex(ValueError,'LEVERAGE_BELOW_100'):
   self.engine.prepare('bad',self.plan)
 def test_pilot_rejects_125x(self):
  self.plan['requestedLeverage']='125';self.must_block()
 def test_pilot_rejects_stop_after_liquidation_scale(self):
  self.plan['orderPreview']['slTriggerPrice']='2462.50';self.must_block()
 def test_pilot_rejects_wrong_quantity(self):
  self.plan['orderPreview']['quantity']='0.01';self.must_block()
 def test_pilot_rejects_wrong_symbol(self):
  self.plan['orderPreview']['symbol']='BTCUSDT';self.must_block()
 def test_pilot_rejects_missing_mark_price(self):
  self.plan['orderPreview']['SlWorkingType']='CONTRACT_PRICE';self.must_block()
 def test_pilot_rejects_stop_above_entry(self):
  self.plan['orderPreview']['slTriggerPrice']='2501';self.must_block()
 def test_pilot_rejects_unknown_reference_price(self):
  self.plan.pop('pilotReferencePrice');self.must_block()
 def test_pilot_rejects_over_notional_cap(self):
  self.plan['pilotReferencePrice']='5100';self.must_block()
if __name__=='__main__':unittest.main()
