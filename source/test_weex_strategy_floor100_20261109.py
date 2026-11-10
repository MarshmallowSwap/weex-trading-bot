"""100x strategy eligibility regressions; no exchange writes."""
import copy,json,tempfile,unittest
from pathlib import Path
from test_weex_pretrade_regression import META
from test_weex_lifecycle import PLAN,Exchange,CFG
from weex_max_leverage import select
from weex_lifecycle import Lifecycle

class StrategyFloor100(unittest.TestCase):
 def select(self,lev,minimum=100):
  return select(metadata={**META,'maxLeverage':lev},
   brackets=[{'notionalFloor':0,'notionalCap':100000,'initialLeverage':lev}],
   margin_usdt=5,reference_price=1,minimum=minimum)
 def test_exchange_maximum_100_is_eligible(self):
  r=self.select(100)
  self.assertEqual(r['leverage'],'100')
  self.assertEqual(r['minimumLeverage'],'100')
  self.assertEqual(r['policy'],'MAXIMUM_LEVERAGE_FIRST_MINIMUM_100')
 def test_maximum_99_is_excluded(self):
  with self.assertRaisesRegex(ValueError,'100_OR_HIGHER'):self.select(99)
 def test_maximum_125_is_not_reduced_to_100(self):
  self.assertEqual(self.select(125)['leverage'],'125')
 def test_configuration_cannot_lower_floor(self):
  with self.assertRaisesRegex(ValueError,'100_OR_HIGHER'):self.select(99,minimum=1)
 def test_configured_floor_higher_than_100_is_preserved(self):
  with self.assertRaises(ValueError):self.select(100,minimum=125)
 def test_lifecycle_accepts_100(self):
  with tempfile.TemporaryDirectory() as d:
   engine=Lifecycle(Path(d)/'test.db',Exchange(),lambda:copy.deepcopy(CFG))
   p=copy.deepcopy(PLAN);p['requestedLeverage']='100'
   self.assertEqual(engine.prepare('floor100',p)['plan']['requestedLeverage'],'100')
 def test_lifecycle_rejects_99(self):
  with tempfile.TemporaryDirectory() as d:
   engine=Lifecycle(Path(d)/'test.db',Exchange(),lambda:copy.deepcopy(CFG))
   p=copy.deepcopy(PLAN);p['requestedLeverage']='99'
   with self.assertRaisesRegex(ValueError,'LEVERAGE_BELOW_100'):engine.prepare('floor99',p)
 def test_configuration_keeps_live_disabled(self):
  cfg=json.loads((Path(__file__).resolve().parent/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
  self.assertEqual(cfg['risk']['minimumLeverage'],100)
  self.assertEqual(cfg['risk']['leveragePreference'],'maximum_settable_cross_minimum_100')
  self.assertFalse(cfg['execution']['enabled'])
  self.assertEqual(cfg['execution']['mode'],'PRETRADE')
if __name__=='__main__':unittest.main()
