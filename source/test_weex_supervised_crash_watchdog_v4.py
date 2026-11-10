"""Fail-closed independent recovery watchdog, no exchange writes."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_supervised_crash_watchdog_v4 import decide,observe

class WatchdogTests(unittest.TestCase):
 def test_no_unknown_entry_never_trades(self):
  r=decide(control_mode='STOPPED',integrity_ok=True,unknown_entry=False)
  self.assertEqual(r['status'],'NO_UNKNOWN_PILOT_ENTRY')
  self.assertFalse(r['safeToResubmitEntry'])
  self.assertEqual(r['exchangeWrites'],0)
 def test_crash_with_uncertain_exchange_readback_never_trades(self):
  r=decide(control_mode='STOPPED',integrity_ok=True,unknown_entry=True,error='TimeoutError')
  self.assertEqual(r['status'],'REVIEW_REQUIRED_READBACK_UNCERTAIN')
  self.assertFalse(r['authorizedToClose'])
 def test_stop_missing_never_authorizes_close(self):
  r=decide(control_mode='STOPPED',integrity_ok=True,unknown_entry=True,
     verification={'status':'STOP_NOT_PROVEN'})
  self.assertEqual(r['status'],'REVIEW_REQUIRED_ENTRY_OR_STOP_UNVERIFIED')
  self.assertFalse(r['authorizedToClose'])
 def test_exact_position_only_requests_separate_authorization(self):
  r=decide(control_mode='STOPPED',integrity_ok=True,unknown_entry=True,
    verification={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE',
      'clientOrderId':'wxentry_foo','positionId':'77','stopAlgoId':'555'})
  self.assertEqual(r['status'],'PROTECTED_EXACT_CLOSE_READY_FOR_SEPARATE_APPROVAL')
  self.assertEqual(r['positionId'],'77')
  self.assertFalse(r['authorizedToClose'])
  self.assertFalse(r['safeToResubmitEntry'])
 def test_running_bot_is_a_critical_block(self):
  r=decide(control_mode='RUNNING',integrity_ok=True,unknown_entry=True,
    verification={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE'})
  self.assertEqual(r['status'],'CRITICAL_CONTROL_OR_INTEGRITY')
 def test_modified_code_is_a_critical_block(self):
  r=decide(control_mode='STOPPED',integrity_ok=False,unknown_entry=True,
    verification={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE'})
  self.assertEqual(r['status'],'CRITICAL_CONTROL_OR_INTEGRITY')
 def test_untrusted_readback_not_assumed(self):
  r=decide(control_mode='STOPPED',integrity_ok=True,unknown_entry=True)
  self.assertEqual(r['status'],'REVIEW_REQUIRED_EXCHANGE_UNVERIFIED')
 def test_standalone_observer_creates_atomic_state(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    r=observe(p,client_id='wxentry_nonexistent')
   self.assertEqual(r['status'],'NO_UNKNOWN_PILOT_ENTRY')
   self.assertEqual(json.loads((p/'weex_supervised_crash_watchdog_latest.json').read_text())['exchangeWrites'],0)
 def test_unknown_entry_queries_checker_but_never_writes(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   con=sqlite3.connect(p/'weex_user_live_lifecycle.sqlite3')
   con.execute('CREATE TABLE writes_v1 (trade_id TEXT,kind TEXT,state TEXT)')
   con.execute("INSERT INTO writes_v1 VALUES('wxentry_test','ENTRY','UNKNOWN')")
   con.commit();con.close()
   queries=[]
   def verifier(client_id,root):
    queries.append(client_id)
    return {'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE',
      'clientOrderId':client_id,'positionId':'77','stopAlgoId':'555'}
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    r=observe(p,checker=verifier,client_id='wxentry_test')
   self.assertEqual(queries,['wxentry_test'])
   self.assertEqual(r['status'],'PROTECTED_EXACT_CLOSE_READY_FOR_SEPARATE_APPROVAL')
   self.assertFalse(r['authorizedToClose'])
 def test_uncertain_checker_requires_review(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   con=sqlite3.connect(p/'weex_user_live_lifecycle.sqlite3')
   con.execute('CREATE TABLE writes_v1 (trade_id TEXT,kind TEXT,state TEXT)')
   con.execute("INSERT INTO writes_v1 VALUES('wxentry_test','ENTRY','UNKNOWN')")
   con.commit();con.close()
   def broken(*args,**kwargs):raise TimeoutError('should never log signed request')
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    r=observe(p,checker=broken,client_id='wxentry_test')
   self.assertEqual(r['status'],'REVIEW_REQUIRED_READBACK_UNCERTAIN')
   self.assertNotIn('signed request',str(r))
if __name__=='__main__':unittest.main()
