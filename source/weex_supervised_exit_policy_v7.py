"""Independent, durable, one-shot PREAUTHORIZED EXIT policy for a single supervised crash.

Never enables entry, never starts the normal bot, and is useless without
proof of a real UNKNOWN production pilot entry and exact attached stop.
Only a separately authorized operator action can create a permit; monitor
cannot grant itself permission. Once claimed, no repeat close POST is allowed.
"""
from __future__ import annotations
import json,sqlite3,time
from contextlib import closing
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_supervised_reduce_only_close_plan_v4 import compose
ROOT=Path(__file__).resolve().parent
DB='weex_supervised_exit_policy_v7.sqlite3'
SCOPE='ETH100_ONE_SHOT_REDUCEONLY_CLOSE_V7'
class ExitDenied(PermissionError):pass
def connect(root):
 c=sqlite3.connect(Path(root)/DB,timeout=8)
 c.execute('PRAGMA busy_timeout=8000')
 c.execute('PRAGMA synchronous=FULL')
 c.execute('CREATE TABLE IF NOT EXISTS approvals (client_id TEXT PRIMARY KEY,scope TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,consumed REAL)')
 return c
def grant(root=ROOT,*,operator_authorized=False,duration=600):
 """Only from separate operator action; no automatic granting by the monitor."""
 import live_control
 root=Path(root)
 if operator_authorized is not True:raise ExitDenied('EXPLICIT_OPERATOR_AUTHORIZATION_REQUIRED')
 if duration<30 or duration>3600:raise ExitDenied('PERMIT_TTL_INVALID')
 if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
  raise ExitDenied('PRODUCTION_MUST_REMAIN_STOPPED_AND_INTEGRITY_PASS')
 with closing(connect(root)) as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM approvals WHERE client_id=?',(CLIENT_ID,)).fetchone():
   c.rollback();raise ExitDenied('PERMISSION_ALREADY_EXISTS_NEVER_REARM')
  at=time.time()
  c.execute('INSERT INTO approvals VALUES(?,?,?,?,?,NULL)',
            (CLIENT_ID,SCOPE,'AUTHORIZED',at,at+duration))
  c.commit()
 return {'status':'EXIT_ONLY_POLICY_GRANTED','scope':SCOPE,'clientId':CLIENT_ID,
         'validSeconds':duration,'entryAllowed':False,'releaseCertified':False}
def status(root=ROOT):
 root=Path(root)
 db=root/DB
 if not db.is_file():return {'status':'NO_EXIT_POLICY','canClose':False}
 try:
  with closing(sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)) as c:
   c.execute('PRAGMA query_only=ON')
   row=c.execute('SELECT scope,status,expires FROM approvals WHERE client_id=?',(CLIENT_ID,)).fetchone()
  if not row:return {'status':'NO_EXIT_POLICY','canClose':False}
  active=row[0]==SCOPE and row[1]=='AUTHORIZED' and 0<row[2]-time.time()<=3600
  return {'status':'EXIT_POLICY_AUTHORIZED' if active else 'EXIT_POLICY_UNAVAILABLE',
          'canClose':bool(active)}
 except Exception:
  return {'status':'EXIT_POLICY_READ_FAILED','canClose':False}
def consume(root,operation,payload,proof):
 """Called only after fresh protected-account readback and exact-close preview."""
 root=Path(root)
 if operation!='post_capi_v3_order':return False
 if not isinstance(payload,dict) or not isinstance(proof,dict):return False
 expect='wxclose_'+CLIENT_ID.split('_',1)[1]
 if (payload.get('symbol')!='ETHUSDT' or payload.get('side')!='SELL'
     or payload.get('positionSide')!='LONG' or payload.get('type')!='MARKET'
     or payload.get('newClientOrderId')!=expect or payload.get('reduceOnly') is not True
     or payload.get('quantity')!='0.001' or
     proof.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE' or
     proof.get('clientOrderId')!=CLIENT_ID or proof.get('symbol')!='ETHUSDT' or
     str(proof.get('quantity')) not in ('0.001','0.0010','0.00100')
     or not str(proof.get('positionId','')).isdigit()
     or not str(proof.get('stopAlgoId','')).isdigit()):
  return False
 if status(root)['canClose'] is not True:return False
 # Permanent, one-shot consumption PRECEDES any network write.
 try:
  with closing(connect(root)) as c:
   c.execute('BEGIN IMMEDIATE')
   r=c.execute('SELECT scope,status,expires FROM approvals WHERE client_id=?',(CLIENT_ID,)).fetchone()
   now=time.time()
   if not r or r[0]!=SCOPE or r[1]!='AUTHORIZED' or not now<r[2]:
    c.rollback();return False
   c.execute('UPDATE approvals SET status=?,consumed=? WHERE client_id=?',
             ('CONSUMED_NO_RETRY',now,CLIENT_ID))
   c.commit()
  return True
 except (sqlite3.Error,OSError):
  return False
def run_exit(root=ROOT,*,sender=None):
 """Real-capable, but only with an unspent separate operator grant and exact proof."""
 root=Path(root)
 if status(root)['canClose'] is not True:
  return {'status':'EXIT_POLICY_NOT_AUTHORIZED','exchangeWrites':0,'releaseCertified':False}
 from weex_supervised_recovery_orchestrator_v6 import dispatch_approved_close
 close=sender or dispatch_approved_close
 try:
  result=close(root=root,operator_approval=lambda op,p,proof:consume(root,op,p,proof))
  if not isinstance(result,dict):raise ExitDenied('UNEXPECTED_CLOSE_RESULT')
  return {**result,'exitPolicy':SCOPE,'releaseCertified':False}
 except Exception as exc:
  return {'status':'EXIT_CLOSE_UNCERTAIN_MANUAL_REVIEW','errorType':type(exc).__name__,
          'entryRetryAllowed':False,'closeRetryAllowed':False,'releaseCertified':False}
if __name__=='__main__':
 print(json.dumps({'status':status(ROOT)['status'],'entryAllowed':False,
                   'closeAllowedOnlyWithOperatorPermit':True,
                   'liveReleaseCertified':False}))
