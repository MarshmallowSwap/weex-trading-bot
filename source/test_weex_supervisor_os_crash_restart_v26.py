"""OS-level crash/restart drill of the REAL independent supervisor process.

Uses a temporary directory and injected observer (zero exchange network).
Kills first process abruptly, spawns a new OS process, verifies heartbeat
PID transition, disarmed state and revocation of stale heartbeat. This is
NOT the live production crash certification.
"""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from weex_supervised_crash_entry_child_v5 import supervisor_ready,process_alive

SOURCE=Path(__file__).resolve().parent
HEALTH='weex_supervised_crash_supervisor_health.json'
CHILD="""import sys
from weex_supervised_process_monitor_v6 import run
run(sys.argv[1],iterations=None,interval=.1,heartbeat_interval=.1,
    observer=lambda root:{'status':'NO_PENDING_CRASH_INTENT'})
"""

def spawn(directory):
 return subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-B','-c',CHILD,str(directory)],
   cwd=str(SOURCE),stdin=subprocess.DEVNULL,
   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def fresh_heartbeat(root,pid,timeout=6):
 path=Path(root)/HEALTH
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  try:
   data=json.loads(path.read_text(encoding='utf-8'))
   if data.get('pid')==pid and time.time()-float(data['heartbeatEpoch'])<2:
    return data
  except (OSError,KeyError,ValueError,TypeError):pass
  time.sleep(.06)
 raise AssertionError('SUPERVISOR_HEARTBEAT_NOT_FRESH')

class SupervisorCrashOSDrill(unittest.TestCase):
 def test_process_kill_then_new_process_recovers_observation_only(self):
  with tempfile.TemporaryDirectory() as td:
   one=spawn(td)
   try:
    first=fresh_heartbeat(td,one.pid)
    self.assertEqual(first['status'],'OBSERVING_NOT_ARMED')
    self.assertFalse(first['entryDispatchAllowed'])
    self.assertFalse(first['closeDispatchAllowed'])
    self.assertFalse(supervisor_ready(td))
    one.kill();one.wait(timeout=6)
    self.assertFalse(process_alive(one.pid))
    # A stale heartbeat from a killed process cannot be used.
    self.assertFalse(supervisor_ready(td))
    two=spawn(td)
    try:
     second=fresh_heartbeat(td,two.pid)
     self.assertNotEqual(one.pid,two.pid)
     self.assertEqual(second['status'],'OBSERVING_NOT_ARMED')
     self.assertFalse(second['entryDispatchAllowed'])
     self.assertFalse(second['closeDispatchAllowed'])
     self.assertFalse(second['releaseCertified'])
     self.assertFalse(supervisor_ready(td))
    finally:
     two.kill();two.wait(timeout=6)
   finally:
    if one.poll() is None:one.kill();one.wait(timeout=6)
 def test_stale_or_fake_ready_not_accepted(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/HEALTH
   p.write_text(json.dumps({'pid':os.getpid(),'heartbeatEpoch':time.time()-90,
      'status':'READY_TO_RECOVER','scope':'ETH100_CRASH_PRODUCTION_WORKER_V5',
      'supportsExactReduceOnlyClose':True,
      'hasIndependentRestartTask':True}))
   self.assertFalse(supervisor_ready(td))

if __name__=='__main__':unittest.main()
