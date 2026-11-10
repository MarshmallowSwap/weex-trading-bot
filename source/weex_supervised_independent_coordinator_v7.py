"""Separate supervised recovery coordinator: real OS-process crash/restart, no exchange writes.

This supervisor NEVER creates trading permits or returns READY_TO_RECOVER.
It verifies that its child was terminated after a durable simulated ACK,
restarts a separate process for read-only recovery, and prevents duplicate
dispatch across restarts.  Real WEEX exposure requires a separate verified
close agent and release attestation; --drill cannot meet that gate.
"""
from __future__ import annotations
import argparse,json,os,sqlite3,subprocess,sys,tempfile,time
from contextlib import closing
from pathlib import Path
from weex_supervised_recovery_watchdog_v5 import reserve,observe_simulated_exchange,offline_reconcile,WatchdogBlocked
from weex_supervised_crash_executor_v2 import CLIENT_ID
ROOT=Path(__file__).resolve().parent
def snapshot(db):
 with closing(sqlite3.connect(db,timeout=8)) as c:
  c.execute('PRAGMA query_only=ON')
  rows=c.execute('SELECT id,operation,state FROM actions ORDER BY id').fetchall()
  exchange=c.execute('SELECT id,kind,state FROM observed_exchange ORDER BY id').fetchall()
 return rows,exchange
def crash_child(db,stage):
 from weex_supervised_recovery_watchdog_v5 import child
 child(db,stage)
def resume_child(db,report):
 from weex_supervised_recovery_watchdog_v5 import offline_reconcile
 state=offline_reconcile(db)
 if state['status'] not in ('PROTECTED_POSITION_REQUIRES_EXACT_CLOSE',
                             'SIMULATED_CLOSE_ACCEPTED_NEEDS_FLAT_AUDIT'):
  raise WatchdogBlocked('INDEPENDENT_RECOVERY_NOT_PROVEN')
 result={'workerPid':os.getpid(),'status':state['status'],
         'entryRetryAllowed':False,'closeRetryAllowed':False,
         'releaseCertified':False,'productionWrites':0}
 Path(report).write_text(json.dumps(result,sort_keys=True)+'\n',encoding='utf-8')
 return result
def drill():
 """A real process death (79), new process GET/SQLite recovery; close death (81), new process recovery."""
 with tempfile.TemporaryDirectory(prefix='weex-real-os-restart-drill-') as td:
  db=Path(td)/'supervised.sqlite3'
  module=str(Path(__file__).resolve())
  command=[sys.executable,'-B',module]
  entry=subprocess.run(command+['--crash-child',str(db),'entry'],
    capture_output=True,text=True,timeout=15)
  if entry.returncode!=79:raise WatchdogBlocked('ENTRY_WORKER_DID_NOT_DIE_AFTER_ACK')
  first=subprocess.run(command+['--resume-child',str(db),str(Path(td)/'first.json')],
    capture_output=True,text=True,timeout=15)
  if first.returncode!=0:raise WatchdogBlocked('RESTART_RECOVERY_PROCESS_FAILED')
  first_state=json.loads((Path(td)/'first.json').read_text(encoding='utf-8'))
  if first_state['status']!='PROTECTED_POSITION_REQUIRES_EXACT_CLOSE':
   raise WatchdogBlocked('RESTART_DID_NOT_VERIFY_EXCHANGE')
  close=subprocess.run(command+['--crash-child',str(db),'close'],
    capture_output=True,text=True,timeout=15)
  if close.returncode!=81:raise WatchdogBlocked('CLOSE_SUPERVISOR_DID_NOT_DIE_AFTER_ACK')
  second=subprocess.run(command+['--resume-child',str(db),str(Path(td)/'second.json')],
    capture_output=True,text=True,timeout=15)
  if second.returncode!=0:raise WatchdogBlocked('CLOSE_RESTART_RECOVERY_PROCESS_FAILED')
  second_state=json.loads((Path(td)/'second.json').read_text(encoding='utf-8'))
  if second_state['status']!='SIMULATED_CLOSE_ACCEPTED_NEEDS_FLAT_AUDIT':
   raise WatchdogBlocked('CLOSE_RECOVERY_NOT_VERIFIED')
  # The same durable client IDs cannot be used again, even in a new process.
  entry_id=CLIENT_ID
  close_id='wxclose_'+CLIENT_ID.split('_',1)[1]
  denied=[]
  for ident,kind in ((entry_id,'ENTRY'),(close_id,'REDUCE_ONLY_CLOSE')):
   try:reserve(db,ident,kind,{'symbol':'ETHUSDT'})
   except WatchdogBlocked as exc:
    if str(exc)!='DURABLE_UNKNOWN_NO_RETRY':raise
    denied.append(ident)
   else:raise WatchdogBlocked('DUPLICATE_DISPATCH_ALLOWED')
  rows,exchange=snapshot(db)
  if len(rows)!=2 or len(exchange)!=2 or len(denied)!=2:
   raise WatchdogBlocked('DURABLE_AUDIT_INCOMPLETE')
  if first_state['workerPid']==os.getpid() or second_state['workerPid']==os.getpid():
   raise WatchdogBlocked('RECOVERY_NOT_SEPARATE_PROCESS')
  return {'status':'INDEPENDENT_OS_PROCESS_RESTART_SIM_PASS',
          'entryExitCode':entry.returncode,'closeExitCode':close.returncode,
          'entryRecoveryNewProcess':True,'closeRecoveryNewProcess':True,
          'durableActions':len(rows),'simulatedExchangeAccepts':len(exchange),
          'duplicateEntryPosts':0,'duplicateClosePosts':0,'realNetworkWrites':0,
          'productionGO':False,'realWorkerCrashCertified':False,
          'remaining':'FINAL_CODE_PATH_SIM_AND_REAL_WORKER_EVIDENCE'}
if __name__=='__main__':
 parser=argparse.ArgumentParser()
 parser.add_argument('--crash-child',nargs=2)
 parser.add_argument('--resume-child',nargs=2)
 parser.add_argument('--drill',action='store_true')
 args=parser.parse_args()
 if args.crash_child:
  crash_child(Path(args.crash_child[0]),args.crash_child[1])
 elif args.resume_child:
  print(json.dumps(resume_child(Path(args.resume_child[0]),Path(args.resume_child[1]))))
 elif args.drill:
  print(json.dumps(drill(),ensure_ascii=False))
 else:
  print(json.dumps({'status':'OFFLINE_SUPERVISOR_ONLY','productionGO':False,'realNetworkWrites':0}))
