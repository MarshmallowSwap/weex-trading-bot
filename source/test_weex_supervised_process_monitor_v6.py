"""Independent read-only monitor tests: heartbeat cannot authorize the pilot."""
import json,os,tempfile,unittest,threading,time
from pathlib import Path
from unittest.mock import patch
from weex_supervised_process_monitor_v6 import tick,run
from weex_supervised_crash_entry_child_v5 import supervisor_ready

class MonitorTests(unittest.TestCase):
 def test_heartbeat_never_arms_real_entry(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   got=tick(root,observer=lambda path:{'status':'NO_PENDING_CRASH_INTENT'})
   self.assertEqual(got['status'],'OBSERVING_NOT_ARMED')
   self.assertFalse(got['supportsExactReduceOnlyClose'])
   self.assertFalse(got['hasIndependentRestartTask'])
   self.assertFalse(supervisor_ready(root))
   self.assertEqual(json.loads((root/'weex_supervised_crash_supervisor_health.json').read_text())['pid'],os.getpid())
 def test_repeated_poll_stays_disarmed(self):
  with tempfile.TemporaryDirectory() as td:
   result=run(td,iterations=3,interval=.1,observer=lambda path:{'status':'UNKNOWN_ENTRY'})
   self.assertEqual(result['iterations'],3)
   self.assertFalse(result['releaseCertified'])
   self.assertFalse(supervisor_ready(td))
 def test_observation_error_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   def fail(path):raise TimeoutError('SECRET')
   out=tick(td,observer=fail)
   self.assertEqual(out['incident'],'OBSERVATION_FAILED_TimeoutError')
   self.assertNotIn('SECRET',json.dumps(out))
   self.assertFalse(supervisor_ready(td))
 def test_proposal_only_when_exact_protected_incident(self):
  with tempfile.TemporaryDirectory() as td:
   called=[]
   def proposal(root):
    called.append(True)
    return {'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'}
   out=tick(td,observer=lambda root:{'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'},
            recovery_planner=proposal)
   self.assertEqual(called,[True])
   self.assertEqual(out['recoveryProposalStatus'],'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION')
   self.assertFalse(out['closeDispatchAllowed'])
   self.assertFalse(supervisor_ready(td))
 def test_unverified_incident_does_not_prepare_close(self):
  with tempfile.TemporaryDirectory() as td:
   def deny(root):raise AssertionError('SHOULD_NOT_BE_CALLED')
   out=tick(td,observer=lambda root:{'status':'UNKNOWN_OR_UNPROTECTED_EXPOSURE'},
            recovery_planner=deny)
   self.assertEqual(out['recoveryProposalStatus'],'NOT_REQUIRED')
   self.assertFalse(out['closeDispatchAllowed'])
 def test_close_outcome_unknown_uses_read_only_reconciler(self):
  import sqlite3
  from contextlib import closing
  from weex_supervised_crash_executor_v2 import CLIENT_ID
  from weex_supervised_reduceonly_close_transport_v4 import STATE
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/STATE
   with closing(sqlite3.connect(db)) as c:
    c.execute('CREATE TABLE intents(entry TEXT PRIMARY KEY,payload TEXT,status TEXT,created REAL)')
    c.execute('INSERT INTO intents VALUES(?,?,?,?)',(CLIENT_ID,'{}','OUTCOME_UNKNOWN',1))
    c.commit()
   invoked=[]
   def recon(root,*,client_id):
    invoked.append(client_id)
    return {'status':'UNKNOWN_CLOSE_ORDER_IN_HISTORY_NO_RETRY'}
   r=tick(td,observer=lambda root:{'status':'UNKNOWN_OR_UNPROTECTED_EXPOSURE'},
          close_reconciler=recon)
   self.assertEqual(invoked,[CLIENT_ID])
   self.assertEqual(r['closeReconciliationStatus'],'UNKNOWN_CLOSE_ORDER_IN_HISTORY_NO_RETRY')
   self.assertFalse(r['closeDispatchAllowed'])
   self.assertFalse(r['supportsExactReduceOnlyClose'])
 def test_live_exit_requires_both_verified_protection_and_operator_permit(self):
  with tempfile.TemporaryDirectory() as td:
   called=[]
   exact=lambda root:{'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'}
   restart_ok=lambda root:{'status':'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS','workerRestartConfirmed':True}
   def fake_exit(root):
    called.append(True)
    return {'status':'FAKE_EXIT_ACK'}
   r=tick(td,observer=lambda root:{'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'},
         recovery_planner=exact,exit_policy_reader=lambda root:{'canClose':False},
         exit_executor=fake_exit,worker_recovery=restart_ok)
   self.assertEqual(called,[])
   self.assertEqual(r['exitPolicyResult'],'NOT_AUTHORIZED')
   self.assertEqual(r['exchangeWrites'],0)
   r=tick(td,observer=lambda root:{'status':'UNKNOWN_OR_UNPROTECTED_EXPOSURE'},
         recovery_planner=exact,exit_policy_reader=lambda root:{'canClose':True},
         exit_executor=fake_exit,worker_recovery=restart_ok)
   self.assertEqual(called,[])
   self.assertEqual(r['exitPolicyResult'],'NOT_REQUIRED')
   r=tick(td,observer=lambda root:{'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'},
         recovery_planner=lambda root:{'status':'BLOCKED_UNVERIFIED_PROTECTION'},
         exit_policy_reader=lambda root:{'canClose':True},exit_executor=fake_exit,worker_recovery=restart_ok)
   self.assertEqual(called,[])
   self.assertEqual(r['exitPolicyResult'],'NOT_REQUIRED')
   r=tick(td,observer=lambda root:{'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'},
         recovery_planner=exact,exit_policy_reader=lambda root:{'canClose':True},exit_executor=fake_exit,worker_recovery=restart_ok)
   self.assertEqual(called,[True])
   self.assertEqual(r['exitPolicyResult'],'FAKE_EXIT_ACK')
   self.assertIsNone(r['exchangeWrites'])
   self.assertEqual(r['possibleReduceOnlyClosePosts'],1)
   self.assertFalse(r['releaseCertified'])
 def test_emergency_close_independent_of_failed_worker_restart(self):
  with tempfile.TemporaryDirectory() as td:
   close_calls=[]
   def emergency(root):
    close_calls.append(True)
    return {'status':'SIMULATED_EXACT_CLOSE_ACK'}
   common=dict(
      observer=lambda root:{'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'},
      recovery_planner=lambda root:{'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'},
      worker_recovery=lambda root:{'status':'RESTART_READBACK_UNVERIFIED','workerRestartConfirmed':False},
      exit_executor=emergency)
   blocked=tick(td,exit_policy_reader=lambda root:{'canClose':False},**common)
   self.assertEqual(close_calls,[])
   self.assertEqual(blocked['exitPolicyResult'],'NOT_AUTHORIZED')
   self.assertEqual(blocked['exchangeWrites'],0)
   result=tick(td,exit_policy_reader=lambda root:{'canClose':True},**common)
   self.assertEqual(result['workerRestartResult'],'RESTART_READBACK_UNVERIFIED')
   self.assertFalse(result['workerRestartConfirmed'])
   self.assertEqual(result['exitPolicyResult'],'SIMULATED_EXACT_CLOSE_ACK')
   self.assertEqual(close_calls,[True])
   self.assertEqual(result['possibleReduceOnlyClosePosts'],1)
   self.assertFalse(result['releaseCertified'])
 def test_heartbeat_renews_even_while_account_readback_blocks(self):
  with tempfile.TemporaryDirectory() as td:
   started=threading.Event();release=threading.Event();output={}
   def slow(root):
    started.set()
    if not release.wait(timeout=4):raise TimeoutError('slow readback')
    return {'status':'NO_PENDING_CRASH_INTENT'}
   def runner():
    output['run']=run(td,iterations=1,interval=.1,heartbeat_interval=.1,observer=slow)
   worker=threading.Thread(target=runner)
   worker.start()
   try:
    self.assertTrue(started.wait(2))
    target=Path(td)/'weex_supervised_crash_supervisor_health.json'
    before=None
    for _ in range(20):
     if target.exists():
      before=json.loads(target.read_text(encoding='utf-8'));break
     time.sleep(.05)
    self.assertIsNotNone(before)
    time.sleep(.4)
    after=json.loads(target.read_text(encoding='utf-8'))
    self.assertGreater(after['heartbeatEpoch'],before['heartbeatEpoch'])
    self.assertEqual(after['status'],'OBSERVING_NOT_ARMED')
    self.assertFalse(after['supportsExactReduceOnlyClose'])
    self.assertTrue(after['pollInProgress'])
   finally:
    release.set();worker.join(timeout=5)
   self.assertFalse(worker.is_alive())
   self.assertEqual(output['run']['iterations'],1)
if __name__=='__main__':unittest.main()
