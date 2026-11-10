"""V33 monitor-to-real-recovery/exit wiring test in isolated runtime.

Uses exact production monitor tick with existing modules' injected callbacks.
The proof inputs are synthetic and none contacts WEEX or grants real permits.
Checks sequential order, retry lockout, missing-approval fail-closed, and
emergency close independence from worker restart; no production state changes.
"""
import tempfile,unittest
from pathlib import Path
from weex_supervised_process_monitor_v6 import tick
INC={'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'}
PROPOSAL={'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'}
RESTART={'status':'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS','workerRestartConfirmed':True}
class OperationalIntegration(unittest.TestCase):
 def run_tick(self,td,events,permit,incident=INC,restart=RESTART,proposal=PROPOSAL):
  def observe(_):
   events.append('incident')
   return incident
  def prepare(_):
   events.append('prepare')
   return proposal
  def read_restart(_):
   events.append('worker_recovery')
   return restart
  def read_exit_policy(_):
   events.append('exit_policy')
   return {'canClose':permit}
  def exit_once(_):
   events.append('exit_once')
   return {'status':'CLOSE_VERIFIED_BY_INDEPENDENT_GET','verifiedFlat':True}
  return tick(td,observer=observe,recovery_planner=prepare,
     worker_recovery=read_restart,exit_policy_reader=read_exit_policy,
     exit_executor=exit_once)
 def test_verified_incident_restarts_and_closes_when_separately_authorized(self):
  with tempfile.TemporaryDirectory() as td:
   events=[]
   r=self.run_tick(td,events,True)
   self.assertEqual(events,['incident','prepare','worker_recovery','exit_policy','exit_once'])
   self.assertEqual(r['workerRestartResult'],'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS')
   self.assertEqual(r['exitPolicyResult'],'CLOSE_VERIFIED_BY_INDEPENDENT_GET')
   self.assertEqual(r['possibleReduceOnlyClosePosts'],1)
   self.assertFalse(r['releaseCertified'])
   self.assertEqual(r['status'],'OBSERVING_NOT_ARMED')
   self.assertFalse(r['entryDispatchAllowed'])
 def test_no_exit_permission_prevents_real_sender(self):
  with tempfile.TemporaryDirectory() as td:
   events=[]
   r=self.run_tick(td,events,False)
   self.assertEqual(events,['incident','prepare','worker_recovery','exit_policy'])
   self.assertEqual(r['exitPolicyResult'],'NOT_AUTHORIZED')
   self.assertEqual(r['exchangeWrites'],0)
 def test_worker_restart_failure_does_not_block_preapproved_emergency_exit(self):
  with tempfile.TemporaryDirectory() as td:
   events=[]
   r=self.run_tick(td,events,True,restart={'status':'RESTART_READBACK_UNVERIFIED','workerRestartConfirmed':False})
   self.assertEqual(events,['incident','prepare','worker_recovery','exit_policy','exit_once'])
   self.assertFalse(r['workerRestartConfirmed'])
   self.assertFalse(r['releaseCertified'])
 def test_incomplete_close_proposal_never_dispatches(self):
  with tempfile.TemporaryDirectory() as td:
   events=[]
   r=self.run_tick(td,events,True,proposal={'status':'BLOCKED_INDEPENDENT_SNAPSHOT'})
   self.assertEqual(events,['incident','prepare'])
   self.assertEqual(r['possibleReduceOnlyClosePosts'],0)
 def test_account_uncertainty_never_restarts_or_sends_exit(self):
  with tempfile.TemporaryDirectory() as td:
   events=[]
   r=self.run_tick(td,events,True,incident={'status':'UNKNOWN_OR_UNPROTECTED_EXPOSURE'})
   self.assertEqual(events,['incident'])
   self.assertEqual(r['exchangeWrites'],0)
   self.assertFalse(r['closeDispatchAllowed'])
if __name__=='__main__':unittest.main()
