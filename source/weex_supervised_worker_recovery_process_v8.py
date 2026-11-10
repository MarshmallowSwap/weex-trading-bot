"""Independent one-shot actual production-worker recovery subprocess.

Only starts the REAL worker in a GET-only --supervised-crash-recovery mode,
never as a strategy executor. Requires real UNKNOWN durable entry and exact
independent exchange proof. Reservation is persisted BEFORE spawn; never retry.
"""
from __future__ import annotations
import hashlib,json,os,sqlite3,subprocess,sys,time
from contextlib import closing
from pathlib import Path
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_supervised_crash_watchdog_v4 import has_unknown_entry
from weex_supervised_real_recovery_v3 import read_exchange
ROOT=Path(__file__).resolve().parent
STATE='weex_supervised_worker_restart_v8.sqlite3'
REPORT='weex_supervised_worker_restart_v8_latest.json'
def reserve(root,client_id):
 with closing(sqlite3.connect(Path(root)/STATE,timeout=8)) as c:
  c.execute('PRAGMA busy_timeout=8000')
  c.execute('PRAGMA synchronous=FULL')
  c.execute('CREATE TABLE IF NOT EXISTS restart (client_id TEXT PRIMARY KEY,state TEXT NOT NULL,created REAL NOT NULL,worker_pid INTEGER,detail TEXT)')
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM restart WHERE client_id=?',(client_id,)).fetchone():
   c.rollback();return False
  c.execute('INSERT INTO restart(client_id,state,created) VALUES(?,?,?)',
            (client_id,'START_OUTCOME_UNKNOWN',time.time()))
  c.commit()
 return True
def save(root,result):
 path=Path(root)/REPORT
 tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 os.replace(tmp,path)
def recover(root=ROOT,*,proof_reader=None,unknown_reader=None,launcher=None,
            control_check=None):
 root=Path(root)
 base={'workerRestartConfirmed':False,'entryRetries':0,'exchangeWrites':0,
       'releaseCertified':False}
 try:
  import live_control
  mode,good=(control_check or (lambda:(
       live_control.state(root)['mode'],not live_control.build_errors(root))))()
  if mode!='STOPPED' or good is not True:
   return {**base,'status':'BLOCKED_PRODUCTION_CONTROL'}
  pending=(unknown_reader or (lambda:has_unknown_entry(root,CLIENT_ID)))()
  if pending is not True:
   return {**base,'status':'NO_DURABLE_UNKNOWN_WORKER_ENTRY'}
  proof=(proof_reader or (lambda:read_exchange(CLIENT_ID,root=root)))()
  if (not isinstance(proof,dict) or proof.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE'
      or proof.get('clientOrderId')!=CLIENT_ID or proof.get('symbol')!='ETHUSDT'
      or str(proof.get('quantity')) not in ('0.001','0.0010','0.00100')
      or not str(proof.get('entryOrderId','')).isdigit()
      or not str(proof.get('positionId','')).isdigit()
      or not str(proof.get('stopAlgoId','')).isdigit()):
   return {**base,'status':'EXCHANGE_ENTRY_STOP_UNVERIFIED'}
  if not reserve(root,CLIENT_ID):
   return {**base,'status':'RECOVERY_PROCESS_ALREADY_RESERVED_NO_RETRY'}
  launch=launcher or (lambda: subprocess.Popen(
      [sys.executable,'-B',str(root/'weex_live_worker.py'),
       '--supervised-crash-recovery'],cwd=str(root),
      stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
  child=None
  try:
   child=launch()
   out,err=child.communicate(timeout=20)
   try:recovered=json.loads(out.strip())
   except (ValueError,TypeError):recovered={}
   valid=(child.returncode==0 and recovered.get('status')=='WORKER_RESTART_PROTECTED_ENTRY_VERIFIED'
          and recovered.get('clientOrderId')==CLIENT_ID
          and all(str(recovered.get(key))==str(proof.get(key)) for key in
                  ('entryOrderId','positionId','stopAlgoId'))
          and recovered.get('entryRetries')==0 and recovered.get('ordersSent')==0)
   result={**base,'status':'INDEPENDENT_REAL_WORKER_READBACK_RESTART_PASS' if valid
           else 'RESTART_READBACK_UNVERIFIED','workerRestartConfirmed':bool(valid),
           'workerPid':child.pid,'supervisorPid':os.getpid(),
           'workerExitCode':child.returncode,
           'workerHashSha256':hashlib.sha256((root/'weex_live_worker.py').read_bytes()).hexdigest()}
  except Exception as exc:
   if child is not None:
    try:child.kill()
    except Exception:pass
   result={**base,'status':'WORKER_RESTART_OUTCOME_UNCERTAIN','errorType':type(exc).__name__}
  with closing(sqlite3.connect(root/STATE,timeout=8)) as c:
   c.execute('UPDATE restart SET state=?,worker_pid=?,detail=? WHERE client_id=?',
             (result['status'],result.get('workerPid'),json.dumps(result,sort_keys=True),CLIENT_ID))
   c.commit()
  save(root,result)
  return result
 except Exception as exc:
  return {**base,'status':'WORKER_RECOVERY_BLOCKED','errorType':type(exc).__name__}
if __name__=='__main__':
 print(json.dumps(recover(),ensure_ascii=False))
