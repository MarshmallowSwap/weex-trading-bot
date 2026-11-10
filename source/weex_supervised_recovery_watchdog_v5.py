"""Standalone supervised crash/restart recovery journal and offline two-crash drill.

Default CLI uses a simulated exchange only; no account keys, network,
trading, or production gate writes. Production interfaces are read-only.
UNKNOWN entry or close is never automatically re-dispatched.
"""
from __future__ import annotations
import json,os,sqlite3,subprocess,sys,tempfile,time
from contextlib import closing
from pathlib import Path
from weex_supervised_crash_executor_v2 import CLIENT_ID,Blocked as PilotBlocked

class WatchdogBlocked(RuntimeError):pass

def connect(path):
 c=sqlite3.connect(path,timeout=8,isolation_level=None)
 c.execute('PRAGMA busy_timeout=8000')
 c.execute('PRAGMA journal_mode=WAL')
 c.execute('CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, operation TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS observed_exchange (id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL)')
 return c

def reserve(path,identity,operation,payload):
 if operation not in ('ENTRY','REDUCE_ONLY_CLOSE'):raise WatchdogBlocked('OPERATION_DENIED')
 if not isinstance(payload,dict) or not payload:raise WatchdogBlocked('INVALID_PAYLOAD')
 with closing(connect(path)) as c:
  c.execute('BEGIN IMMEDIATE')
  try:
   if c.execute('SELECT 1 FROM actions WHERE id=?',(identity,)).fetchone():
    raise WatchdogBlocked('DURABLE_UNKNOWN_NO_RETRY')
   c.execute('INSERT INTO actions VALUES(?,?,?,?)',(identity,operation,'UNKNOWN',json.dumps(payload,sort_keys=True)))
   c.execute('COMMIT')
  except BaseException:
   c.execute('ROLLBACK');raise
 return True

def observe_simulated_exchange(path,identity,kind,payload):
 """Mock external exchange acknowledgement in a different table and durable commit."""
 with closing(connect(path)) as c:
  c.execute('BEGIN IMMEDIATE')
  try:
   action=c.execute('SELECT operation,state,payload FROM actions WHERE id=?',(identity,)).fetchone()
   if not action or action!=(kind,'UNKNOWN',json.dumps(payload,sort_keys=True)):
    raise WatchdogBlocked('EXCHANGE_DISPATCH_NOT_JOURNALED')
   if c.execute('SELECT 1 FROM observed_exchange WHERE id=?',(identity,)).fetchone():
    raise WatchdogBlocked('EXCHANGE_DUPLICATE')
   c.execute('INSERT INTO observed_exchange VALUES(?,?,?,?)',(identity,kind,'ACCEPTED',json.dumps(payload,sort_keys=True)))
   c.execute('COMMIT')
  except BaseException:
   c.execute('ROLLBACK');raise
 return {'accepted':True}

def offline_reconcile(path,entry_id=CLIENT_ID):
 """Never send a network write. Distinguish unknown, protected, uncertain close."""
 with closing(connect(path)) as c:
  entry=c.execute('SELECT operation,state,payload FROM actions WHERE id=?',(entry_id,)).fetchone()
  if not entry or entry[0]!='ENTRY' or entry[1]!='UNKNOWN':
   return {'status':'BLOCKED_ENTRY_JOURNAL','entryRetryAllowed':False,'closeRetryAllowed':False}
  ex_entry=c.execute('SELECT kind,state,payload FROM observed_exchange WHERE id=?',(entry_id,)).fetchone()
  if ex_entry is None or ex_entry[0]!='ENTRY' or ex_entry[1]!='ACCEPTED' or ex_entry[2]!=entry[2]:
   return {'status':'UNKNOWN_ENTRY_STOP_ENTRIES','entryRetryAllowed':False,'closeRetryAllowed':False}
  payload=json.loads(entry[2])
  if (payload.get('newClientOrderId')!=entry_id or payload.get('symbol')!='ETHUSDT'
      or payload.get('quantity')!='0.001' or payload.get('SlWorkingType')!='MARK_PRICE'
      or not payload.get('slTriggerPrice')):
   return {'status':'UNVERIFIED_ENTRY_STOP_ENTRIES','entryRetryAllowed':False,'closeRetryAllowed':False}
  close_id='wxclose_'+entry_id.split('_',1)[1]
  close=c.execute('SELECT operation,state,payload FROM actions WHERE id=?',(close_id,)).fetchone()
  if close is None:
   return {'status':'PROTECTED_POSITION_REQUIRES_EXACT_CLOSE',
     'entryRetryAllowed':False,'closeRetryAllowed':False,'hasUnknownClose':False}
  ex_close=c.execute('SELECT kind,state,payload FROM observed_exchange WHERE id=?',(close_id,)).fetchone()
  if close[0]!='REDUCE_ONLY_CLOSE' or close[1]!='UNKNOWN':
   return {'status':'UNTRUSTED_CLOSE_JOURNAL','entryRetryAllowed':False,'closeRetryAllowed':False}
  if ex_close is None:
   return {'status':'UNKNOWN_CLOSE_READBACK_REQUIRED','entryRetryAllowed':False,
     'closeRetryAllowed':False,'hasUnknownClose':True}
  if ex_close[0]!='REDUCE_ONLY_CLOSE' or ex_close[1]!='ACCEPTED' or ex_close[2]!=close[2]:
   return {'status':'AMBIGUOUS_CLOSE_BLOCKED','entryRetryAllowed':False,
     'closeRetryAllowed':False,'hasUnknownClose':True}
  return {'status':'SIMULATED_CLOSE_ACCEPTED_NEEDS_FLAT_AUDIT',
     'entryRetryAllowed':False,'closeRetryAllowed':False,'hasUnknownClose':True}

def child(path,stage):
 entry={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
   'quantity':'0.001','newClientOrderId':CLIENT_ID,
   'SlWorkingType':'MARK_PRICE','slTriggerPrice':'2093.00'}
 closeid='wxclose_'+CLIENT_ID.split('_',1)[1]
 close={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
  'type':'MARKET','quantity':'0.001','newClientOrderId':closeid,'reduceOnly':True}
 if stage=='entry':
  reserve(path,CLIENT_ID,'ENTRY',entry)
  observe_simulated_exchange(path,CLIENT_ID,'ENTRY',entry)
  os._exit(79)
 if stage=='close':
  observed=offline_reconcile(path)
  if observed['status']!='PROTECTED_POSITION_REQUIRES_EXACT_CLOSE':
   raise WatchdogBlocked('NO_VERIFIED_POSITION_FOR_CLOSE')
  reserve(path,closeid,'REDUCE_ONLY_CLOSE',close)
  observe_simulated_exchange(path,closeid,'REDUCE_ONLY_CLOSE',close)
  os._exit(81)
 raise WatchdogBlocked('INVALID_TEST_STAGE')

def drill():
 with tempfile.TemporaryDirectory(prefix='weex-two-crashes-') as tmp:
  db=Path(tmp)/'watchdog.sqlite3'
  args=[sys.executable,'-B',str(Path(__file__).resolve()),'--child',str(db)]
  first=subprocess.run(args+['entry'],capture_output=True,text=True,timeout=12)
  if first.returncode!=79:raise WatchdogBlocked('ENTRY_OS_CRASH_NOT_OBSERVED')
  result=offline_reconcile(db)
  if result['status']!='PROTECTED_POSITION_REQUIRES_EXACT_CLOSE':
   raise WatchdogBlocked('ENTRY_RECOVERY_NOT_VERIFIED')
  second=subprocess.run(args+['close'],capture_output=True,text=True,timeout=12)
  if second.returncode!=81:raise WatchdogBlocked('SUPERVISOR_OS_CRASH_NOT_OBSERVED')
  recovered=offline_reconcile(db)
  if recovered['status']!='SIMULATED_CLOSE_ACCEPTED_NEEDS_FLAT_AUDIT':
   raise WatchdogBlocked('SUPERVISOR_CLOSE_RECOVERY_FAILED')
  entry={ 'symbol':'ETHUSDT','quantity':'0.001' }
  try:reserve(db,CLIENT_ID,'ENTRY',entry)
  except WatchdogBlocked as exc:
   if str(exc)!='DURABLE_UNKNOWN_NO_RETRY':raise
  else:raise WatchdogBlocked('DUPLICATE_ENTRY_PERMITTED')
  closeid='wxclose_'+CLIENT_ID.split('_',1)[1]
  try:reserve(db,closeid,'REDUCE_ONLY_CLOSE',entry)
  except WatchdogBlocked as exc:
   if str(exc)!='DURABLE_UNKNOWN_NO_RETRY':raise
  else:raise WatchdogBlocked('DUPLICATE_CLOSE_PERMITTED')
  with closing(connect(db)) as c:
   actions=c.execute('SELECT operation,state FROM actions ORDER BY operation').fetchall()
   external=c.execute('SELECT kind,state FROM observed_exchange ORDER BY kind').fetchall()
  if len(actions)!=2 or len(external)!=2:raise WatchdogBlocked('WRONG_DISPATCH_COUNTS')
  return {'status':'OFFLINE_DOUBLE_OS_CRASH_PASS','workerCrashExit':79,
   'supervisorCrashExit':81,'durableIntents':2,
   'simulatedExchangeAccepts':2,'duplicateEntries':0,'duplicateCloses':0,
   'restoredAfterSupervisorRestart':True,'requiresIndependentFlatAudit':True,
   'realNetworkRequests':0,'realOrdersSubmitted':0,
   'realReleaseCertified':False}

if __name__=='__main__':
 if len(sys.argv)==4 and sys.argv[1]=='--child':
  child(Path(sys.argv[2]),sys.argv[3])
 elif len(sys.argv)==2 and sys.argv[1]=='--drill':
  print(json.dumps(drill(),ensure_ascii=False))
 else:
  print(json.dumps({'status':'OFFLINE_RECOVERY_WATCHDOG_ONLY',
   'realOrderDispatchAvailable':False,'realCloseDispatchAvailable':False}))
