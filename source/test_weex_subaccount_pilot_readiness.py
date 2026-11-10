"""Offline subaccount pilot preflight must never infer safety from an empty wallet."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_subaccount_pilot_readiness import inspect
SAMPLE_CFG={'environment':'live_requested_not_enabled','risk':{'marginModePreference':'cross','stopLoss':{'enabled':False}},'execution':{}}

class SubaccountPilot(unittest.TestCase):
 def exercise(self,positions=None,orders=None,algos=None,gate=False):
  with tempfile.TemporaryDirectory() as dirname:
   root=Path(dirname)
   (root/'live_release_gate_latest.json').write_text(json.dumps({
    'gate':'GO' if gate else 'NO_GO','checks':{'crash_restart_recovery_live_tested':gate}}))
   with patch('weex_subaccount_pilot_readiness.live_control.state',return_value={'mode':'STOPPED'}),\
        patch('weex_subaccount_pilot_readiness.live_control.configuration',return_value=(SAMPLE_CFG,'digest')),\
        patch('weex_subaccount_pilot_readiness.live_control.build_errors',return_value=[]):
    return inspect(root,get_account=lambda:(positions or [],orders or [],algos or []))
 def test_empty_main_wallet_not_sufficient(self):
  x=self.exercise()
  self.assertFalse(x['liveTradingAuthorized'])
  self.assertIn('exchangeSubaccountSeparated',x['blockers'])
  self.assertIn('subaccountCollateralLimitVerified',x['blockers'])
 def test_go_gate_does_not_override_unverified_subaccount(self):
  x=self.exercise(gate=True)
  self.assertFalse(x['checks']['exchangeSubaccountSeparated'])
  self.assertFalse(x['liveTradingAuthorized'])
 def test_existing_position_blocks_pilot(self):
  x=self.exercise(positions=[{'symbol':'ETHUSDT','side':'LONG','size':'1','id':'1'}])
  self.assertIn('noExistingPositions',x['blockers'])
 def test_pending_order_blocks_pilot(self):
  x=self.exercise(orders=[{'symbol':'ETHUSDT'}])
  self.assertIn('noPendingRegularOrders',x['blockers'])
 def test_failed_account_read_does_not_issue_dispatch(self):
  with tempfile.TemporaryDirectory() as dirname:
   root=Path(dirname)
   with patch('weex_subaccount_pilot_readiness.live_control.state',return_value={'mode':'STOPPED'}),\
        patch('weex_subaccount_pilot_readiness.live_control.configuration',return_value=(SAMPLE_CFG,'digest')):
    with self.assertRaises(ValueError):
     inspect(root,get_account=lambda:(None,[],[]))
 def test_running_mode_blocks_before_api(self):
  with patch('weex_subaccount_pilot_readiness.live_control.state',return_value={'mode':'RUNNING'}):
   with self.assertRaises(PermissionError):
    inspect(Path('.'),get_account=lambda:(_ for _ in ()).throw(AssertionError('network unexpectedly used')))
if __name__=='__main__':unittest.main()
