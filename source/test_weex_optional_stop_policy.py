import unittest
from weex_optional_stop_policy import assess
from weex_live_new_entry_guard import evaluate as entry
BASE={'environment':'live_requested_not_enabled',
 'risk':{'stopLoss':{'enabled':False},'marginModePreference':'isolated'},
 'strategySettings':{'slMode':'off'},
 'execution':{'allowOrdersWithoutStop':True}}
class OptionalStop(unittest.TestCase):
 def test_optional_off_is_consistent(self):
  x=assess(BASE)
  self.assertTrue(x['valid']);self.assertFalse(x['stopOrderRequired'])
  self.assertFalse(x['canAuthorizeLive'])
 def test_optional_mode_not_a_preflight_error(self):
  self.assertTrue(entry(BASE,[],[],[])['allowed'])
  self.assertFalse(entry(BASE,[],[],[])['authorizesNetworkWrite'])
 def test_enabled_stop_is_valid(self):
  c={**BASE,'risk':{'stopLoss':{'enabled':True},'marginModePreference':'isolated'},
   'strategySettings':{'slMode':'percent'},
   'execution':{'allowOrdersWithoutStop':False}}
  self.assertTrue(assess(c)['valid'])
 def test_inconsistent_blocks(self):
  c={**BASE,'risk':{'stopLoss':{'enabled':True},'marginModePreference':'isolated'}}
  self.assertFalse(assess(c)['valid'])
  self.assertIn('INCONSISTENT_OPTIONAL_SL_SETTINGS',entry(c,[],[],[])['issues'])
 def test_cross_margin_separate_risk_block(self):
  c={**BASE,'risk':{'stopLoss':{'enabled':False},'marginModePreference':'cross'}}
  self.assertIn('SHARED_CROSS_MARGIN_UNCERTIFIED',entry(c,[],[],[])['issues'])
if __name__=='__main__':unittest.main()
