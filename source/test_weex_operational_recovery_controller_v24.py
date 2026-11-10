"""Fail-closed operational prearm tests, no exchange or operator authority."""
import tempfile,time,unittest
from pathlib import Path
from weex_operational_recovery_controller_v24 import assess

XML='''<?xml version="1.0" encoding="utf-8"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
 <Principals><Principal><LogonType>S4U</LogonType></Principal></Principals>
 <Settings><RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure></Settings>
 <Actions><Exec><Command>python.exe</Command><Arguments>weex_supervised_process_monitor_v6.py --loop</Arguments></Exec></Actions>
</Task>'''
def snapshot():
 t=time.time()
 return {'complete':True,'startedAtMs':int((t-1)*1000),
         'completedAtMs':int((t-.5)*1000),'positions':[],
         'regularOrders':[],'conditionalOrders':[],'trailingOrders':[]}
def audit(**kwargs):
 t=time.time()
 data=dict(task_xml=XML,health={'scope':'ETH100_CRASH_PRODUCTION_WORKER_V5',
  'status':'OBSERVING_NOT_ARMED','heartbeatEpoch':t,'entryDispatchAllowed':False},
  task_running=True,live_pid=True,integrity_pass=True,exit_permit=True,
  sdk_close=True,api_headroom=True,snapshot=snapshot(),now=t)
 data.update(kwargs)
 return assess(**data)
class Controller(unittest.TestCase):
 def test_nominal_never_overclaims_live(self):
  r=audit()
  self.assertTrue(r['taskVerified'])
  self.assertTrue(r['monitorLive'])
  self.assertTrue(r['accountFlatForNewCrossEntry'])
  self.assertFalse(r['readyToRecover'])
  self.assertFalse(r['mayPublishReadyHeartbeat'])
  self.assertIn('INDEPENDENT_PROCESS_RESTART_AND_EXIT_DRILL_NOT_ATTESTED',r['blockers'])
 def test_manual_cross_blocks_even_with_permit(self):
  s=snapshot()
  s['positions']=[{'id':'99','symbol':'AINUSDT'}]
  s['conditionalOrders']=[{'algoId':'33','symbol':'AINUSDT'}]
  r=audit(snapshot=s)
  self.assertIn('SHARED_CROSS_COLLATERAL_OCCUPIED',r['blockers'])
  self.assertFalse(r['entryAllowed'])
 def test_exit_permission_missing(self):
  self.assertIn('INDEPENDENT_ONE_SHOT_EXIT_PERMIT_REQUIRED',
                audit(exit_permit=False)['blockers'])
 def test_readonly_observation_stale(self):
  s=snapshot()
  s['startedAtMs']-=30000;s['completedAtMs']-=30000
  self.assertIn('FRESH_COMPLETE_CROSS_SNAPSHOT_REQUIRED',audit(snapshot=s)['blockers'])
 def test_s4u_no_restart(self):
  bad=XML.replace('<RestartOnFailure>','<RestartNotEnabled>').replace('</RestartOnFailure>','</RestartNotEnabled>')
  self.assertIn('INDEPENDENT_S4U_MONITOR_TASK_UNVERIFIED',audit(task_xml=bad)['blockers'])
 def test_heartbeat_pid_stale_or_forged(self):
  h={'scope':'ETH100_CRASH_PRODUCTION_WORKER_V5','status':'READY_TO_RECOVER',
     'heartbeatEpoch':time.time(),'entryDispatchAllowed':True}
  self.assertIn('INDEPENDENT_MONITOR_HEARTBEAT_UNVERIFIED',audit(health=h)['blockers'])
  self.assertIn('INDEPENDENT_MONITOR_HEARTBEAT_UNVERIFIED',audit(live_pid=False)['blockers'])
 def test_api_and_sdk_fail_closed(self):
  self.assertIn('WEEX_RECOVERY_API_HEADROOM_UNVERIFIED',audit(api_headroom=False)['blockers'])
  self.assertIn('EXACT_REDUCE_ONLY_CLOSE_PREVIEW_REQUIRED',audit(sdk_close=False)['blockers'])
 def test_missing_snapshot_never_grants(self):
  r=audit(snapshot=None)
  self.assertFalse(r['accountFlatForNewCrossEntry'])
  self.assertFalse(r['closeAllowed'])
if __name__=='__main__':unittest.main()
