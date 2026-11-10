"""Exercise the REAL worker CLI recovery branch as an OS subprocess.

All WEEX reads are replaced before CLI execution and all state is in a temp
directory; no live exchange, no real permit, no production journal mutation.
This proves process control, identity checks and no-retry, NOT live crash.
"""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from weex_supervised_worker_recovery_process_v8 import recover
from weex_supervised_crash_executor_v2 import CLIENT_ID

SOURCE=Path(__file__).resolve().parent/'weex_live_worker.py'
PROOF={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
       'symbol':'ETHUSDT','quantity':'0.001','entryOrderId':'123',
       'positionId':'456','stopAlgoId':'789'}
# import production modules in the child, then replace the two functions
# which would access the real switch or WEEX GET; run the unaltered worker.
CHILD_SCRIPT="""import sys,runpy,json
import live_control
import weex_supervised_real_recovery_v3 as real
from weex_supervised_crash_executor_v2 import CLIENT_ID
live_control.state=lambda root:{'mode':'STOPPED'}
live_control.build_errors=lambda root:[]
proof=json.loads(sys.argv[2])
real.read_exchange=lambda client_id,root=None:proof
sys.argv=[sys.argv[1],'--supervised-crash-recovery']
runpy.run_path(sys.argv[0],run_name='__main__')
"""

def launch(proof):
 def invoke():
  return subprocess.Popen([sys.executable,'-B','-c',CHILD_SCRIPT,str(SOURCE),json.dumps(proof)],
      cwd=str(SOURCE.parent),stdin=subprocess.DEVNULL,
      stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 return invoke

def execute(root,proof=PROOF,unknown=True):
 return recover(root,unknown_reader=lambda:unknown,
        proof_reader=lambda:proof,
        control_check=lambda:('STOPPED',True),launcher=launch(proof))

class RealWorkerSubprocessIntegration(unittest.TestCase):
 def test_true_worker_branch_restarts_with_exact_no_write_proof(self):
  with tempfile.TemporaryDirectory() as td:
   # Only the hash input, not the original production file, is copied.
   (Path(td)/'weex_live_worker.py').write_bytes(SOURCE.read_bytes())
   r=execute(td)
   self.assertEqual(r['status'],'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS',r)
   self.assertTrue(r['workerRestartConfirmed'])
   self.assertEqual(r['workerExitCode'],0)
   self.assertNotEqual(r['workerPid'],os.getpid())
   self.assertEqual(r['entryRetries'],0)
   self.assertEqual(r['exchangeWrites'],0)
   self.assertEqual(execute(td)['status'],'RECOVERY_PROCESS_ALREADY_RESERVED_NO_RETRY')
 def test_mismatched_real_worker_readback_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   (Path(td)/'weex_live_worker.py').write_bytes(SOURCE.read_bytes())
   bad=dict(PROOF,entryOrderId='999')
   r=recover(td,unknown_reader=lambda:True,
      proof_reader=lambda:PROOF,control_check=lambda:('STOPPED',True),
      launcher=launch(bad))
   self.assertEqual(r['status'],'RESTART_READBACK_UNVERIFIED',r)
   self.assertFalse(r['workerRestartConfirmed'])
   self.assertEqual(r['exchangeWrites'],0)
 def test_unknown_not_in_real_journal_prevents_launch(self):
  with tempfile.TemporaryDirectory() as td:
   r=execute(td,unknown=False)
   self.assertEqual(r['status'],'NO_DURABLE_UNKNOWN_WORKER_ENTRY')
   self.assertFalse((Path(td)/'weex_supervised_worker_restart_v8.sqlite3').exists())
 def test_unverified_stop_prevents_launch(self):
  with tempfile.TemporaryDirectory() as td:
   r=execute(td,proof=dict(PROOF,stopAlgoId=''))
   self.assertEqual(r['status'],'EXCHANGE_ENTRY_STOP_UNVERIFIED')
   self.assertEqual(r['exchangeWrites'],0)

if __name__=='__main__':unittest.main()
