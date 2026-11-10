"""Offline tests for durable one-shot GET-only actual worker subprocess."""
import json,tempfile,unittest,subprocess,sys,os
from pathlib import Path
from weex_supervised_worker_recovery_process_v8 import recover
from weex_supervised_crash_executor_v2 import CLIENT_ID
PROOF={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
       'symbol':'ETHUSDT','quantity':'0.001',
       'entryOrderId':'123','positionId':'456','stopAlgoId':'789'}
class Child:
 pid=39876;returncode=0
 def communicate(self,timeout):
  return json.dumps({'status':'WORKER_RESTART_PROTECTED_ENTRY_VERIFIED',
       'clientOrderId':CLIENT_ID,'entryOrderId':'123','positionId':'456','stopAlgoId':'789',
       'entryRetries':0,'ordersSent':0}), ''
 def kill(self):pass
def check(root,*,unknown=True,proof=PROOF,launcher=lambda:Child()):
 return recover(root,unknown_reader=lambda:unknown,proof_reader=lambda:proof,
                control_check=lambda:('STOPPED',True),launcher=launcher)
class ProcessRecoveryTests(unittest.TestCase):
 def test_no_unknown_no_spawn(self):
  with tempfile.TemporaryDirectory() as td:
   r=check(td,unknown=False,launcher=lambda:1/0)
   self.assertEqual(r['status'],'NO_DURABLE_UNKNOWN_WORKER_ENTRY')
 def test_unverified_stop_no_spawn(self):
  with tempfile.TemporaryDirectory() as td:
   r=check(td,proof={},launcher=lambda:1/0)
   self.assertEqual(r['status'],'EXCHANGE_ENTRY_STOP_UNVERIFIED')
 def test_process_verified_and_no_retry(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'weex_live_worker.py').write_text('offline worker',encoding='utf-8')
   first=check(td)
   self.assertEqual(first['status'],'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS')
   self.assertTrue(first['workerRestartConfirmed'])
   self.assertFalse(first['releaseCertified'])
   second=check(td,launcher=lambda:1/0)
   self.assertEqual(second['status'],'RECOVERY_PROCESS_ALREADY_RESERVED_NO_RETRY')
 def test_mismatched_order_prevents_verified_restart(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'weex_live_worker.py').write_text('offline worker',encoding='utf-8')
   class Bad(Child):
    def communicate(self,timeout):
     return json.dumps({'status':'WORKER_RESTART_PROTECTED_ENTRY_VERIFIED',
                         'clientOrderId':CLIENT_ID,'entryOrderId':'999',
                         'positionId':'456','stopAlgoId':'789','entryRetries':0,
                         'ordersSent':0}), ''
   r=check(td,launcher=lambda:Bad())
   self.assertEqual(r['status'],'RESTART_READBACK_UNVERIFIED')
   self.assertFalse(r['workerRestartConfirmed'])
 def test_wrong_protected_position_identity_prevents_spawn(self):
  with tempfile.TemporaryDirectory() as td:
   for bad in (dict(PROOF,clientOrderId='wrong'),dict(PROOF,quantity='0.01'),
               dict(PROOF,stopAlgoId=''),dict(PROOF,symbol='BTCUSDT'),
               dict(PROOF,entryOrderId=None)):
    with self.subTest(bad=bad):
     r=check(td,proof=bad,launcher=lambda:1/0)
     self.assertEqual(r['status'],'EXCHANGE_ENTRY_STOP_UNVERIFIED')
 def test_actual_os_subprocess_restart_and_durable_no_retry(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'weex_live_worker.py').write_text('offline worker mock, NOT production',encoding='utf-8')
   result={'status':'WORKER_RESTART_PROTECTED_ENTRY_VERIFIED','clientOrderId':CLIENT_ID,
     'entryOrderId':'123','positionId':'456','stopAlgoId':'789',
     'entryRetries':0,'ordersSent':0}
   script='import json;print(json.dumps('+repr(result)+'))'
   def start_child():
    return subprocess.Popen([sys.executable,'-B','-c',script],cwd=td,
       stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   first=check(td,launcher=start_child)
   self.assertEqual(first['status'],'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS')
   self.assertNotEqual(first['workerPid'],os.getpid())
   self.assertEqual(first['workerExitCode'],0)
   self.assertEqual(check(td,launcher=lambda:1/0)['status'],
                    'RECOVERY_PROCESS_ALREADY_RESERVED_NO_RETRY')
if __name__=='__main__':unittest.main()
