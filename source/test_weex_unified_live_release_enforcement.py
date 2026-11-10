"""Fail-closed release gating of Telegram arming and final dispatch."""
import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
import live_control

class GateEnforcementTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.work=live_control.connect(self.root)
  self.work.execute("UPDATE switch_v1 SET mode='RUNNING',generation=1 WHERE id=1")
  self.work.commit();self.work.close()
  self.write_gate('NO_GO')
 def write_gate(self,state):
  checks={'crash_restart_recovery_live_tested':state=='GO'}
  (self.root/'live_release_gate_latest.json').write_text(json.dumps({
    'checkedAt':datetime.now(timezone.utc).isoformat(),'gate':state,'checks':checks,
    'passed':int(state=='GO'),'total':1,'ordersPlacedByAudit':False}))
 def test_no_go_fails_before_network_dispatch(self):
  with patch('live_control.configuration',return_value=({},'hash')),patch('live_control.build_errors',return_value=[]):
   with self.assertRaisesRegex(PermissionError,'LIVE_RELEASE_NOT_CERTIFIED'):
    with live_control.dispatch_permission(self.root,1,'hash'):
     self.fail('Must never reach network-enabled body')
 def test_stale_go_fails_closed(self):
  self.write_gate('GO')
  g=json.loads((self.root/'live_release_gate_latest.json').read_text())
  g['checkedAt']='2000-01-01T00:00:00+00:00'
  (self.root/'live_release_gate_latest.json').write_text(json.dumps(g))
  with patch('live_control.configuration',return_value=({},'hash')),patch('live_control.build_errors',return_value=[]):
   with self.assertRaisesRegex(PermissionError,'LIVE_RELEASE_NOT_CERTIFIED'):
    with live_control.dispatch_permission(self.root,1,'hash'):pass
 def test_readiness_reports_independent_no_go(self):
  (self.root/'weex_live_worker_latest.json').write_text(json.dumps({
    'checkedAt':datetime.now(timezone.utc).isoformat(),
    'accountReadOK':True,'recoveryClear':True,'host':'https://api-contract.weex.com'}))
  with patch('live_control.configuration',return_value=({},'hash')),patch('live_control.build_errors',return_value=[]):
   self.assertIn('LIVE_RELEASE_NO_GO',live_control.readiness(self.root))
if __name__=='__main__':unittest.main()
