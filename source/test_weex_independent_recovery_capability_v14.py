"""Negative/offline checks: an audit cannot grant entry or close permissions."""
import json,time,unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from weex_independent_recovery_capability_v14 import check

XML='''<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Principals><Principal><LogonType>S4U</LogonType></Principal></Principals><Settings><RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure></Settings><Actions><Exec><Arguments>-B weex_supervised_process_monitor_v6.py --loop</Arguments></Exec></Actions></Task>'''
def heartbeat(age=1,pid=111):
 return {'pid':pid,'heartbeatEpoch':time.time()-age,
         'status':'OBSERVING_NOT_ARMED','entryDispatchAllowed':False,
         'closeDispatchAllowed':False}
class CapabilityTests(unittest.TestCase):
 def invoke(self,xml=XML,h=None,alive=True):
  with TemporaryDirectory() as td,patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]),patch('weex_independent_recovery_capability_v14.prepare_sdk_request',return_value={'state':'STOPPED_BEFORE_NETWORK','networkRequests':0,'sdkSerializationVerified':True}),patch('weex_independent_recovery_capability_v14.exit_status',return_value={'canClose':False}),patch('weex_independent_recovery_capability_v14.has_unknown_entry',return_value=False):
   return check(Path(td),task_xml=xml,health=h if h is not None else heartbeat(),
                liveness=lambda pid:alive,headroom=lambda:True)
 def test_even_good_infrastructure_never_arms_orders(self):
  r=self.invoke()
  self.assertTrue(r['taskS4UVerified'] and r['supervisorHeartbeatLive'])
  self.assertFalse(r['entryDispatchAllowed'])
  self.assertFalse(r['closeDispatchAllowed'])
  self.assertFalse(r['releaseCertified'])
  self.assertEqual(r['exchangeWrites'],0)
 def test_stale_heartbeat_blocks(self):
  self.assertIn('LIVE_SUPERVISOR_HEARTBEAT_UNVERIFIED',
                self.invoke(h=heartbeat(age=100))['blockers'])
 def test_disconnected_pid_blocks(self):
  self.assertFalse(self.invoke(alive=False)['supervisorHeartbeatLive'])
 def test_non_s4u_task_blocks(self):
  r=self.invoke(xml=XML.replace('<LogonType>S4U','<LogonType>InteractiveToken'))
  self.assertFalse(r['taskS4UVerified'])
 def test_missing_exit_permit_and_journal_never_count_as_ready(self):
  r=self.invoke()
  self.assertIn('INDEPENDENT_ONE_SHOT_EXIT_PERMIT_MISSING',r['blockers'])
  self.assertIn('REAL_WORKER_UNKNOWN_JOURNAL_MISSING',r['blockers'])
if __name__=='__main__':unittest.main()
