"""Independent fail-closed recovery monitor for one exact WEEX crash pilot.

GET-only by default. With an independently granted, unspent one-shot EXIT
permit and verified protected entry + worker restart, it can invoke a single
real reduceOnly close; never opens a position or arms the strategy worker.
Heartbeat stays OBSERVING_NOT_ARMED until full live certification.
"""
from __future__ import annotations
import argparse,json,os,signal,sys,time,threading
from datetime import datetime,timezone
from pathlib import Path
from weex_independent_incident_supervisor_v6 import observe,ROOT

HEALTH='weex_supervised_crash_supervisor_health.json'
AUDIT='weex_supervised_process_monitor_v6_latest.json'
def atomic_json(path,data):
 path=Path(path);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.tmp')
 tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 # Windows readers may briefly hold the target with restrictive sharing.
 # Retry a bounded number of times; never report heartbeat success if the
 # atomic replacement remains blocked.
 try:
  for attempt in range(8):
   try:
    os.replace(tmp,path)
    return
   except PermissionError:
    if attempt==7:raise
    time.sleep(.025*(attempt+1))
 finally:
  try:tmp.unlink(missing_ok=True)
  except OSError:pass

def tick(root=ROOT,*,observer=observe,clock=time.time,recovery_planner=None,close_reconciler=None,exit_policy_reader=None,exit_executor=None,worker_recovery=None):
 """One bounded read-only poll; never tells V5 it is READY_TO_RECOVER."""
 root=Path(root)
 try:
  report=observer(root)
  incident=report.get('status','UNKNOWN')
 except Exception as exc:
  incident='OBSERVATION_FAILED_'+type(exc).__name__
 proposal='NOT_REQUIRED'
 if incident=='VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL':
  try:
   if recovery_planner is None:
    from weex_supervised_recovery_orchestrator_v6 import prepare
    recovery_planner=prepare
   plan=recovery_planner(root)
   proposal=plan.get('status','UNKNOWN') if isinstance(plan,dict) else 'INVALID_PROPOSAL'
  except Exception as exc:
   proposal='BLOCKED_PLANNER_'+type(exc).__name__
 restart_status='NOT_REQUIRED'
 worker_restarted=False
 if (incident=='VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'
     and proposal=='EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'):
  try:
   if worker_recovery is None:
    from weex_supervised_worker_recovery_process_v8 import recover
    worker_recovery=recover
   restarted=worker_recovery(root)
   restart_status=restarted.get('status','UNKNOWN') if isinstance(restarted,dict) else 'INVALID'
   worker_restarted=(isinstance(restarted,dict) and restarted.get('status')=='INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS'
                     and restarted.get('workerRestartConfirmed') is True)
   if restart_status=='RECOVERY_PROCESS_ALREADY_RESERVED_NO_RETRY':
    # Recovery was already attempted: do not spawn again. Only a durable
    # previously verified readback for the current exact worker build counts.
    import json,hashlib
    previous=root/'weex_supervised_worker_restart_v8_latest.json'
    if previous.is_file():
     saved=json.loads(previous.read_text(encoding='utf-8'))
     worker_restarted=(saved.get('status')=='INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS'
        and saved.get('workerRestartConfirmed') is True
        and saved.get('workerHashSha256')==hashlib.sha256((root/'weex_live_worker.py').read_bytes()).hexdigest())
  except Exception as exc:
   restart_status='BLOCKED_RESTART_'+type(exc).__name__
 exit_status='NOT_REQUIRED'
 exit_attempted=False
 # An emergency EXIT must not depend on the crashed worker being restartable.
 # The separate verifier and the exit transport each re-check the exact
 # protected position/stop, and the exit permit is one-shot and preauthorized.
 if (incident=='VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL' and
     proposal=='EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'):
  try:
   if exit_policy_reader is None:
    from weex_supervised_exit_policy_v7 import status
    exit_policy_reader=status
   permission=exit_policy_reader(root)
   if not isinstance(permission,dict) or permission.get('canClose') is not True:
    exit_status='NOT_AUTHORIZED'
   else:
    if exit_executor is None:
     from weex_supervised_exit_policy_v7 import run_exit
     exit_executor=run_exit
    # Potential single reduceOnly network write; reservation is consumed
    # before dispatch. Any ambiguous outcome requires readback, not retry.
    exit_attempted=True
    result=exit_executor(root)
    exit_status=result.get('status','UNKNOWN_EXIT_RESULT') if isinstance(result,dict) else 'INVALID_EXIT_RESULT'
  except Exception as exc:
   exit_status='BLOCKED_EXIT_'+type(exc).__name__
 close_recovery='NOT_REQUIRED'
 try:
  from weex_supervised_reduceonly_close_transport_v4 import STATE
  from weex_supervised_crash_executor_v2 import CLIENT_ID
  from contextlib import closing
  import sqlite3
  close_db=root/STATE
  if close_db.is_file():
   with closing(sqlite3.connect('file:'+close_db.resolve().as_posix()+'?mode=ro',uri=True)) as c:
    c.execute('PRAGMA query_only=ON')
    row=c.execute('SELECT status FROM intents WHERE entry=?',(CLIENT_ID,)).fetchone()
   if row and row[0]=='OUTCOME_UNKNOWN':
    if close_reconciler is None:
     from weex_supervised_exact_close_readback_v6 import recover_lost_close_ack
     close_reconciler=recover_lost_close_ack
    evidence=close_reconciler(root,client_id=CLIENT_ID)
    close_recovery=evidence.get('status','UNKNOWN') if isinstance(evidence,dict) else 'INVALID'
 except Exception as exc:
  close_recovery='BLOCKED_CLOSE_RECONCILIATION_'+type(exc).__name__
 msg={'status':'OBSERVING_NOT_ARMED','scope':'ETH100_CRASH_PRODUCTION_WORKER_V5',
      'pid':os.getpid(),'heartbeatEpoch':float(clock()),
      'supportsExactReduceOnlyClose':False,'hasIndependentRestartTask':False,
      'independentProcess':True,'exchangeWrites':None if exit_attempted else 0,
      'possibleReduceOnlyClosePosts':1 if exit_attempted else 0,
      'entryDispatchAllowed':False,'closeDispatchAllowed':False,
      'releaseCertified':False,'incident':incident,'recoveryProposalStatus':proposal,
      'workerRestartResult':restart_status,'workerRestartConfirmed':worker_restarted,
      'exitPolicyResult':exit_status,'closeReconciliationStatus':close_recovery}
 atomic_json(root/HEALTH,msg)
 atomic_json(root/AUDIT,dict(msg,checkedAt=datetime.now(timezone.utc).isoformat()))
 return msg

def run(root=ROOT,*,iterations=1,interval=2,observer=observe,heartbeat_interval=2):
 if iterations is not None and (not isinstance(iterations,int) or iterations<1):
  raise ValueError('INVALID_ITERATIONS')
 if not .1<=interval<=60:raise ValueError('INVALID_POLL_INTERVAL')
 if not .1<=heartbeat_interval<=5:raise ValueError('INVALID_HEARTBEAT_INTERVAL')
 root=Path(root)
 stop=threading.Event()
 lock=threading.Lock()
 shared={'last':None,'pollInProgress':True}
 def heartbeat():
  # Separate from potentially slow authenticated GETs and worker startup.
  # Never claims operational readiness based only on OS liveness.
  while not stop.is_set():
   with lock:
    previous=dict(shared['last'] or {})
    busy=shared['pollInProgress']
   previous.update(status='OBSERVING_NOT_ARMED',
     scope='ETH100_CRASH_PRODUCTION_WORKER_V5',
     pid=os.getpid(),heartbeatEpoch=time.time(),
     supportsExactReduceOnlyClose=False,hasIndependentRestartTask=False,
     entryDispatchAllowed=False,closeDispatchAllowed=False,
     releaseCertified=False,pollInProgress=busy)
   atomic_json(root/HEALTH,previous)
   stop.wait(heartbeat_interval)
 thread=threading.Thread(target=heartbeat,name='weex-readonly-heartbeat',daemon=True)
 thread.start()
 count=0;last=None;possible_close_posts=0
 try:
  while iterations is None or count<iterations:
   with lock:shared['pollInProgress']=True
   last=tick(root,observer=observer)
   with lock:
    shared['last']=last
    shared['pollInProgress']=False
   possible_close_posts+=last.get('possibleReduceOnlyClosePosts',0)
   count+=1
   if iterations is None or count<iterations:stop.wait(interval)
 finally:
  stop.set()
  thread.join(timeout=5)
 return {'status':'RECOVERY_MONITOR_RUN_COMPLETE','iterations':count,
         'lastIncident':last['incident'],
         'exchangeWrites':0 if possible_close_posts==0 else None,
         'possibleReduceOnlyClosePosts':possible_close_posts,
         'releaseCertified':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser()
 ap.add_argument('--iterations',type=int,default=1)
 ap.add_argument('--loop',action='store_true')
 ap.add_argument('--interval',type=float,default=2)
 args=ap.parse_args()
 print(json.dumps(run(iterations=None if args.loop else args.iterations,
                      interval=args.interval),ensure_ascii=False))
