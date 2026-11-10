"""No-network security regressions for recurring Telegram COLLAUDO."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from weex_telegram_collaudo import diagnose,format_telegram

class CollaudoTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.root=Path(self.folder.name)
  (self.root/'weex_ai_risk_config.json').write_text(json.dumps({'execution':{'enabled':False,'mode':'PRETRADE'}}))
  (self.root/'live_release_gate_latest.json').write_text(json.dumps({
   'checkedAt':datetime.now(timezone.utc).isoformat(),'gate':'NO_GO','passed':9,'total':10,
   'checks':{'book':True,'crash_restart_recovery_live_tested':False}}))
 def probe(self,name,root,timeout):
  if name=='weex_worker_crash_probe_test_20261109.py':
   return {'status':'PASS','childExitCode':79,'duplicateEntries':0,
    'recoveredState':'PROTECTED','networkRequests':0,'liveOrders':0}
  return {'positions':0,'orders':0,'conditional':0,'unresolvedWrites':[],'integrity':[]}
 def test_safe_diagnostic_does_not_approve_live(self):
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   x=diagnose(self.root,self.probe)
  self.assertEqual(x['status'],'CHECKS_PASS_NO_REAL_ACTIVATION')
  self.assertFalse(x['realCrashCertified'])
  self.assertFalse(x['tradingEnabledByCollaudo'])
  self.assertFalse(x['productionOrdersAuthorized'])
  self.assertEqual(x['exchangeWrites'],0)
  self.assertEqual(x['gatePassed'],9)
  self.assertIn('Nessun ordine inviato',format_telegram(x))
 def test_live_switch_blocks_crash_probe(self):
  calls=[]
  def probe(name,root,timeout):
   calls.append(name)
   if name=='weex_worker_crash_probe_test_20261109.py':raise AssertionError('CRASH_TEST_WHILE_RUNNING')
   return {'positions':0,'orders':0,'conditional':0,'unresolvedWrites':[],'integrity':[]}
  with patch('live_control.state',return_value={'mode':'RUNNING'}),patch('live_control.build_errors',return_value=[]):
   x=diagnose(self.root,probe)
  self.assertEqual(x['status'],'ATTENTION')
  self.assertNotIn('weex_worker_crash_probe_test_20261109.py',calls)
 def test_incomplete_account_is_attention(self):
  def bad(name,root,timeout):
   if name=='weex_worker_crash_probe_test_20261109.py':return self.probe(name,root,timeout)
   return {'error':'API_TIMEOUT'}
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   x=diagnose(self.root,bad)
  self.assertFalse(x['accountClear']);self.assertEqual(x['status'],'ATTENTION')
 def test_integrity_fail_closed(self):
  calls=[]
  def probe(name,root,timeout):
   calls.append(name)
   return {'error':'NOT_READY'}
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=['CHANGED']):
   x=diagnose(self.root,probe)
  self.assertEqual(x['status'],'ATTENTION')
  self.assertNotIn('weex_worker_crash_probe_test_20261109.py',calls)
 def test_never_go_from_demo_crash_only(self):
  (self.root/'live_release_gate_latest.json').write_text(json.dumps({
   'checkedAt':datetime.now(timezone.utc).isoformat(),'gate':'GO','passed':10,'total':10,
   'checks':{'crash_restart_recovery_live_tested':True}}))
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   x=diagnose(self.root,self.probe)
  self.assertFalse(x['tradingEnabledByCollaudo'])
  self.assertFalse(x['productionOrdersAuthorized'])
  self.assertEqual(x['exchangeWrites'],0)
if __name__=='__main__':unittest.main()
