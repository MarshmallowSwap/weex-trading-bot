"""Bounded Cross trial policy: no exchange requests, no live authorization."""
import copy,unittest
from weex_live_new_entry_guard import evaluate
BASE={'environment':'live_requested_not_enabled',
 'risk':{'stopLoss':{'enabled':False},'marginModePreference':'cross',
         'entryBudgetMode':'COST_INCLUDING_ENTRY_FEE','orderCostTargetUSDT':'15',
         'minimumLeverage':125},
 'strategySettings':{'slMode':'off','tpMode':'fixed','tpAccountingMode':'GROSS_BEFORE_COSTS',
                     'targetNetProfitUSDT':30},
 'execution':{'allowOrdersWithoutStop':True,'enabled':False,'mode':'PRETRADE'},
 'telegramSettings':{'maxConcurrentPositions':{'default':3}}}
class CrossTrialTests(unittest.TestCase):
 def test_flat_scope_veto_passes_but_never_sends(self):
  r=evaluate(BASE,[],[],[])
  self.assertTrue(r['allowed'],r['issues'])
  self.assertFalse(r['authorizesNetworkWrite'])
 def test_existing_position_always_blocks(self):
  p=[{'id':'pos1','symbol':'ETHUSDT','side':'LONG','size':'0.002'}]
  self.assertFalse(evaluate(BASE,p,[],[])['allowed'])
 def test_existing_tp_always_blocks(self):
  self.assertFalse(evaluate(BASE,[],[],[{'symbol':'ETHUSDT'}])['allowed'])
 def test_existing_order_always_blocks(self):
  self.assertFalse(evaluate(BASE,[],[{'symbol':'ETHUSDT'}],[])['allowed'])
 def test_budget_above_15_blocks(self):
  c=copy.deepcopy(BASE);c['risk']['orderCostTargetUSDT']='15.01'
  self.assertIn('SHARED_CROSS_MARGIN_UNCERTIFIED',evaluate(c,[],[],[])['issues'])
 def test_min_leverage_above_125_blocks(self):
  c=copy.deepcopy(BASE);c['risk']['minimumLeverage']=200
  self.assertFalse(evaluate(c,[],[],[])['allowed'])
 def test_nonfinite_amount_blocks(self):
  c=copy.deepcopy(BASE);c['risk']['orderCostTargetUSDT']='NaN'
  self.assertFalse(evaluate(c,[],[],[])['allowed'])
 def test_different_tp_blocks(self):
  c=copy.deepcopy(BASE);c['strategySettings']['targetNetProfitUSDT']=31
  self.assertFalse(evaluate(c,[],[],[])['allowed'])
 def test_auto_execution_flag_blocks(self):
  c=copy.deepcopy(BASE);c['execution']['enabled']=True
  self.assertFalse(evaluate(c,[],[],[])['allowed'])
if __name__=='__main__':unittest.main()
