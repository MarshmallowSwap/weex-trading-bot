"""Replay a prior WEEX API-SIM crash through INDEPENDENT supervisor OS process.

Evidence is a completed, authenticated API-SIM incident report. A replay is
NOT a new WEEX API execution and NOT proof of production worker readback
against live WEEX. Independent supervisor uses actual production tick(),
real v8 one-shot recovery and actual worker CLI --supervised-crash-recovery
with ONLY its exchange-read function injected from archived SIM proof.
No external requests, live permits, or real account mutations.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from weex_supervised_process_monitor_v6 import tick
from weex_supervised_worker_recovery_process_v8 import recover
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_demo_evidence_acceptance_v32 import classify

ROOT=Path(__file__).resolve().parent
EVIDENCE='weex_demo_supervisor_bridge_v34_result.json'
REAL_WORKER=ROOT/'weex_live_worker.py'
CHILD_CODE="""import sys,runpy,json
import live_control
import weex_supervised_real_recovery_v3 as reader
from weex_supervised_crash_executor_v2 import CLIENT_ID
proof=json.loads(sys.argv[2])
live_control.state=lambda root:{'mode':'STOPPED'}
live_control.build_errors=lambda root:[]
reader.read_exchange=lambda client_id,root=None:proof
sys.argv=[sys.argv[1],'--supervised-crash-recovery']
runpy.run_path(sys.argv[0],run_name='__main__')
"""
def archived_proof(d):
 if (d.get('host')!='https://api-sim.weex.com'
     or d.get('status')!='DEMO_SUPERVISOR_TICK_EXIT_PASS'
     or d.get('childExitCode')!=73
     or d.get('observedEntries')!=1
     or d.get('stopVerified') is not True
     or d.get('exactEntryVerified') is not True
     or d.get('noDuplicateEntry') is not True
     or d.get('closeAcknowledged') is not True
     or d.get('accountFlat') is not True
     or d.get('demoEntryPOSTs')!=1 or d.get('demoClosePOSTs')!=1
     or d.get('realOrders')!=0 or d.get('retries')!=0
     or not str(d.get('entryOrderId','')).isdigit()
     or not str(d.get('childState',{}).get('clientId',''))==str(d.get('clientOrderId'))
     or d.get('childState',{}).get('stage')!='ENTRY_OUTCOME_UNKNOWN'):
  raise ValueError('ARCHIVED_SIM_EVIDENCE_INCOMPLETE')
 # Offline adapter maps archived demo IDs to production recovery schema.
 # This does not assert the demo trade was created by production worker.
 if not str(d.get('closeOrderId','')).isdigit():raise ValueError('DEMO_CLOSE_ID_INVALID')
 return {'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE',
  'clientOrderId':CLIENT_ID,'symbol':'ETHUSDT','quantity':'0.001',
  'entryOrderId':str(d['entryOrderId']),
  'positionId':'456','stopAlgoId':'789'}
def run(root,record,*,allow_demo_close=True,override_proof=None):
 root=Path(root)
 if root.resolve()==ROOT.resolve():
  raise PermissionError('PRODUCTION_ROOT_PROHIBITED')
 if not root.exists():raise ValueError('TEMP_ROOT_REQUIRED')
 if (root/'weex_credentials.json').exists():raise PermissionError('NO_PRODUCTION_CREDENTIALS')
 evidence=json.loads(Path(record).read_text(encoding='utf-8'))
 proof=archived_proof(evidence) if override_proof is None else override_proof
 if not (root/'weex_live_worker.py').exists():
  (root/'weex_live_worker.py').write_bytes(REAL_WORKER.read_bytes())
 events=[]
 def observer(_):
  events.append('observe_archived_demo')
  return {'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'}
 def plan(_):
  events.append('prepare_from_archived_demo')
  return {'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'}
 def launcher():
  events.append('spawn_real_worker_cli')
  return subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-B','-c',
    CHILD_CODE,str(REAL_WORKER),json.dumps(proof)],cwd=str(ROOT),stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 def recover_worker(_):
  events.append('recover_v8')
  return recover(root,unknown_reader=lambda:True,
   proof_reader=lambda:proof,control_check=lambda:('STOPPED',True),
   launcher=launcher)
 def permission(_):
  events.append('demo_only_permission')
  return {'canClose':allow_demo_close}
 close_events=[]
 def close(_):
  events.append('archived_close_readback_no_network')
  # Durable reservation in the isolated root, BEFORE interpreting evidence.
  # A second supervisor process cannot claim the same archived exit again.
  claim=root/'weex_demo_close_v35_reserved_once'
  try:
   fd=os.open(str(claim),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  except FileExistsError:
   return {'status':'DEMO_EXIT_ALREADY_RESERVED_NO_RETRY','verifiedFlat':False}
  with os.fdopen(fd,'w') as f:f.write(str(os.getpid()))
  close_events.append('verified')
  return {'status':'CLOSE_VERIFIED_BY_INDEPENDENT_GET' if evidence.get('accountFlat')
          else 'CLOSE_READBACK_UNCERTAIN','verifiedFlat':evidence.get('accountFlat') is True}
 result=tick(root,observer=observer,recovery_planner=plan,
  worker_recovery=recover_worker,exit_policy_reader=permission,
  exit_executor=close)
 report={'status':'INDEPENDENT_OS_SUPERVISOR_REPLAY_PASS'
         if result.get('workerRestartConfirmed') is True and
            result.get('exitPolicyResult')=='CLOSE_VERIFIED_BY_INDEPENDENT_GET' and
            len(close_events)==1 else 'INDEPENDENT_REPLAY_INCOMPLETE',
   'supervisorPid':os.getpid(),'workerPid':None,'events':events,
   'workerRestartResult':result.get('workerRestartResult'),
   'workerRestartConfirmed':result.get('workerRestartConfirmed'),
   'exitResult':result.get('exitPolicyResult'),
   'demoEvidenceHost':evidence['host'],'archivedDemoOrderId':evidence['entryOrderId'],
   'productionWorkerCodeUsed':True,'productionWorkerExchangeReaderReplaced':True,
   'realPostAckCrashTest':False,'newApiSimPosts':0,'productionPosts':0,
   'realExitPermitUsed':False,'liveReleaseCertified':False,
   'readyToRecover':False,'supervisorHealthStatus':result['status']}
 restart_file=root/'weex_supervised_worker_restart_v8_latest.json'
 if restart_file.exists():
  r=json.loads(restart_file.read_text(encoding='utf-8'))
  report['workerPid']=r.get('workerPid')
  report['workerCodeHash']=r.get('workerHashSha256')
 report['reportPath']=str(root/'weex_supervisor_replay_v35_result.json')
 (root/'weex_supervisor_replay_v35_result.json').write_text(
  json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
 return report

if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('NEED_ISOLATED_ROOT_AND_ARCHIVE')
 print(json.dumps(run(sys.argv[1],sys.argv[2]),ensure_ascii=False))
