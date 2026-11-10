import unittest
from weex_live_new_entry_guard import evaluate
C={'environment':'live_requested_not_enabled',
   'risk':{'stopLoss':{'enabled':True},'marginModePreference':'isolated'},
   'strategySettings':{'slMode':'percent'},
   'execution':{'allowOrdersWithoutStop':False}}
class LiveEntry(unittest.TestCase):
 def test_config_unprotected_blocked(self):
  c={**C,'risk':{'stopLoss':{'enabled':False},'marginModePreference':'cross'},
     'strategySettings':{'slMode':'off'},'execution':{'allowOrdersWithoutStop':True}}
  x=evaluate(c,[],[],[])
  self.assertFalse(x['allowed'])
  self.assertNotIn('STOP_LOSS_DISABLED',x['issues'])
  self.assertNotIn('INCONSISTENT_OPTIONAL_SL_SETTINGS',x['issues'])
  self.assertIn('SHARED_CROSS_MARGIN_UNCERTIFIED',x['issues'])
 def test_manual_exposure_blocks(self):
  self.assertFalse(evaluate(C,[{'id':9,'symbol':'BTCUSDT','side':'LONG','size':'1'}],[],[])['allowed'])
 def test_unattributed_tp_blocks(self):
  self.assertFalse(evaluate(C,[],[],[{'symbol':'BTCUSDT'}])['allowed'])
 def test_regular_open_order_blocks(self):
  self.assertFalse(evaluate(C,[],[{'symbol':'ETHUSDT'}],[])['allowed'])
 def test_clean_config_does_not_itself_authorize_order(self):
  x=evaluate(C,[],[],[])
  self.assertTrue(x['allowed'])
  self.assertFalse(x['authorizesNetworkWrite'])
 def test_corrupt_snapshots_fail_closed(self):
  self.assertFalse(evaluate(C,None,[],[])['allowed'])
if __name__=='__main__':unittest.main()
