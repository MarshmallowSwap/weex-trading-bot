import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from weex_os_crash_journal_drill import run as drill
from weex_cross_margin_risk_audit import audit

class LocalCrashDrill(unittest.TestCase):
 def test_real_process_exit_recovery_is_not_live_proof(self):
  x=drill()
  self.assertEqual(x['status'],'REAL_OS_CRASH_LOCAL_JOURNAL_VERIFIED')
  self.assertEqual(len(x['checks']),3)
  self.assertFalse(x['liveExchangeCrashCertified'])
  self.assertTrue(all(z['sqliteIntents']==1 and z['ordersSubmitted']==0 for z in x['checks']))

class CrossRiskAudit(unittest.TestCase):
 def test_current_cross_has_no_certified_loss_limit(self):
  with tempfile.TemporaryDirectory() as d:
   config={'risk':{'marginModePreference':'cross','stopLoss':{'enabled':False},
                    'minimumLeverage':125,'orderCostTargetUSDT':'30',
                    'initialMarginTargetUSDT':5},
          'strategySettings':{},
          'telegramSettings':{'maxConcurrentPositions':{'default':3}},
          'execution':{'allowOrdersWithoutStop':True}}
   with patch('weex_cross_margin_risk_audit.live_control.configuration',return_value=(config,'digest')):
    x=audit(d)
   self.assertFalse(x['lossCeilingCertified'])
   self.assertFalse(x['canClearCrossGuardianBlock'])
   self.assertFalse(x['positionLossLimitGuaranteedByMargin'])
   self.assertIn('NO_STOP_CAN_LOSE_SHARED_ACCOUNT_COLLATERAL',x['issues'])
 def test_dedicated_cross_account_is_not_isolated_per_position(self):
  with tempfile.TemporaryDirectory() as d:
   c={'risk':{'marginModePreference':'cross','stopLoss':{'enabled':True},
       'minimumLeverage':25,'orderCostTargetUSDT':'5',
       'initialMarginTargetUSDT':5},
      'strategySettings':{},'execution':{'allowOrdersWithoutStop':False},
      'telegramSettings':{'maxConcurrentPositions':{'default':1}}}
   with patch('weex_cross_margin_risk_audit.live_control.configuration',return_value=(c,'digest')):
    x=audit(d)
   self.assertFalse(x['canEnableLive'])
   self.assertFalse(x['independentCollateralForEachPosition'])
   self.assertFalse(x['canClearCrossGuardianBlock'])
if __name__=='__main__':unittest.main()
