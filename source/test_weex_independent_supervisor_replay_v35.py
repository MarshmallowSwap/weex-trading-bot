"""V35 real OS supervisor replay audit with fail closed evidence and approvals."""
import json,tempfile,unittest
from pathlib import Path
from weex_independent_supervisor_replay_v35 import run,archived_proof,ROOT,EVIDENCE
from weex_supervised_crash_executor_v2 import CLIENT_ID
PATH=ROOT/EVIDENCE
class IndependentReplay(unittest.TestCase):
 def test_true_os_linked_monitor_real_worker_branch_once(self):
  with tempfile.TemporaryDirectory() as td:
   a=run(td,PATH)
   self.assertEqual(a['status'],'INDEPENDENT_OS_SUPERVISOR_REPLAY_PASS',a)
   self.assertTrue(a['workerRestartConfirmed'])
   self.assertEqual(a['events'],['observe_archived_demo','prepare_from_archived_demo',
        'recover_v8','spawn_real_worker_cli','demo_only_permission',
        'archived_close_readback_no_network'])
   self.assertNotEqual(a['supervisorPid'],a['workerPid'])
   self.assertEqual(a['productionPosts'],0)
   self.assertEqual(a['newApiSimPosts'],0)
   self.assertFalse(a['readyToRecover'])
   self.assertFalse(a['liveReleaseCertified'])
   b=run(td,PATH)
   self.assertEqual(b['workerRestartResult'],'RECOVERY_PROCESS_ALREADY_RESERVED_NO_RETRY')
   self.assertEqual(b['exitResult'],'DEMO_EXIT_ALREADY_RESERVED_NO_RETRY')
   self.assertNotIn('spawn_real_worker_cli',b['events'])
 def test_no_demo_permission_blocks_exit(self):
  with tempfile.TemporaryDirectory() as td:
   r=run(td,PATH,allow_demo_close=False)
   self.assertEqual(r['exitResult'],'NOT_AUTHORIZED')
   self.assertFalse((Path(td)/'weex_demo_close_v35_reserved_once').exists())
 def test_invalid_demo_evidence_cannot_run(self):
  raw=json.loads(PATH.read_text(encoding='utf-8'))
  for key,value in [('host','https://api-contract.weex.com'),('stopVerified',False),
                    ('childExitCode',0),('demoEntryPOSTs',2)]:
   changed=dict(raw,**{key:value})
   with self.assertRaises(ValueError):archived_proof(changed)
 def test_bad_exact_proof_denies_worker_recovery(self):
  with tempfile.TemporaryDirectory() as td:
   e=json.loads(PATH.read_text(encoding='utf-8'))
   proof=archived_proof(e)
   proof['stopAlgoId']=''
   r=run(td,PATH,override_proof=proof)
   self.assertFalse(r['workerRestartConfirmed'])
   self.assertEqual(r['workerRestartResult'],'EXCHANGE_ENTRY_STOP_UNVERIFIED')
   self.assertEqual(r['productionPosts'],0)
 def test_production_root_is_forbidden(self):
  with self.assertRaises(PermissionError):run(ROOT,PATH)
if __name__=='__main__':unittest.main()
