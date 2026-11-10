"""Durable read-only Guardian for WEEX partial-exit replacement.

SQLite WAL/FULL, immutable trade binding, audited steps. This component
NEVER executes, queues or retries exchange writes. A step is *planned*
only; recording an attempt locks it until authenticated exchange
readback validates the outcome. Crashes never trigger order resubmission.
"""
import hashlib,json,sqlite3,time
from contextlib import closing
from pathlib import Path
from weex_partial_exit_replace_guard import inspect

STEPS=('PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK',
       'CANCEL_EXACT_OLD_STOP_SIM_ONLY_THEN_READBACK',
       'RECONCILE_OR_CANCEL_EXACT_OLD_TP_SIM_ONLY',
       'PLACE_RESIDUAL_TP_SIM_ONLY_THEN_READBACK')
STATUSES={
 'NEEDS_NEW_STOP_FIRST_OFFLINE':STEPS[0],
 'DUPLICATE_STOPS_REVIEW':STEPS[1],
 'NEW_STOP_ONLY_OLD_TP_REVIEW':STEPS[2],
 'NEW_STOP_PRESENT_TP_MISSING':STEPS[3]}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def dbopen(path):
 db=sqlite3.connect(path,timeout=10,isolation_level=None)
 db.row_factory=sqlite3.Row
 db.execute('PRAGMA journal_mode=WAL')
 db.execute('PRAGMA synchronous=FULL')
 db.execute('CREATE TABLE IF NOT EXISTS replacements (trade_id TEXT PRIMARY KEY, binding TEXT NOT NULL, sha TEXT NOT NULL, phase TEXT NOT NULL, pending TEXT, last_proof TEXT)')
 db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT,trade_id TEXT NOT NULL, event TEXT NOT NULL, digest TEXT NOT NULL, created_ms INTEGER NOT NULL)')
 return db
def record(db,tid,kind,detail):
 db.execute('INSERT INTO events(trade_id,event,digest,created_ms) VALUES(?,?,?,?)',
            (tid,kind,hashlib.sha256(canonical(detail).encode()).hexdigest(),int(time.time()*1000)))
def register(path,tid,*,position_id,symbol,side,old_tp_client,old_sl_client,new_tp_client,new_sl_client):
 if not isinstance(tid,str) or not tid or not position_id or not symbol or side not in ('LONG','SHORT'):
  raise ValueError('INVALID_BINDING')
 cids=(old_tp_client,old_sl_client,new_tp_client,new_sl_client)
 if any(not isinstance(x,str) or not x for x in cids) or len(set(cids))!=4:
  raise ValueError('EXIT_IDENTITIES_MUST_BE_UNIQUE')
 binding=dict(positionId=str(position_id),symbol=symbol,side=side,
              old_tp_client=old_tp_client,old_sl_client=old_sl_client,
              new_tp_client=new_tp_client,new_sl_client=new_sl_client)
 h=hashlib.sha256(canonical(binding).encode()).hexdigest()
 with closing(dbopen(path)) as db:
  db.execute('BEGIN IMMEDIATE')
  try:
   prev=db.execute('SELECT * FROM replacements WHERE trade_id=?',(tid,)).fetchone()
   if prev and prev['sha']!=h:raise ValueError('IMMUTABLE_GUARDIAN_BINDING_CHANGED')
   if not prev:
    db.execute('INSERT INTO replacements VALUES(?,?,?,?,NULL,NULL)',(tid,canonical(binding),h,'REGISTERED'))
    record(db,tid,'REGISTERED',binding)
   db.execute('COMMIT')
   return {'state':prev['phase'] if prev else 'REGISTERED','existing':bool(prev),'canDispatch':False}
  except Exception:
   db.execute('ROLLBACK');raise
def evaluate(path,tid,*,positions,algos,regular_orders,authenticated_sim_readback=False):
 base={'state':'REVIEW_REQUIRED','canDispatch':False,'canRetry':False,'liveEnabled':False}
 with closing(dbopen(path)) as db:
  db.execute('BEGIN IMMEDIATE')
  try:
   row=db.execute('SELECT * FROM replacements WHERE trade_id=?',(tid,)).fetchone()
   if row is None:raise ValueError('UNKNOWN_TRADE')
   binding=json.loads(row['binding'])
   if not authenticated_sim_readback:raise ValueError('NO_TRUSTED_SIM_READBACK')
   if not isinstance(positions,list) or not isinstance(algos,list) or not isinstance(regular_orders,list):
    raise ValueError('INVALID_SNAPSHOT')
   matches=[p for p in positions if str(p.get('id'))==binding['positionId']]
   if len(matches)!=1:raise ValueError('POSITION_NOT_UNIQUELY_PRESENT')
   observed=inspect(position=matches[0],algos=algos,regular_orders=regular_orders,
      expected_position_id=binding['positionId'],old_tp_client=binding['old_tp_client'],
      old_sl_client=binding['old_sl_client'],new_tp_client=binding['new_tp_client'],
      new_sl_client=binding['new_sl_client'])
   if observed['status']=='REVIEW_REQUIRED':raise ValueError(observed.get('reason','REVIEW_REQUIRED'))
   # If a write was attempted but not independently accounted for, no new instruction.
   if row['pending'] is not None:
    intended=json.loads(row['pending'])
    if observed['status']==intended['before']:
     raise ValueError('PREVIOUS_ATTEMPT_NOT_RESOLVED')
    # Changed state does not certify the intended operation. Every
    # transition requires independent check by an exchange-aware executor.
    db.execute('UPDATE replacements SET phase=?,last_proof=? WHERE trade_id=?',
               ('CHANGED_AFTER_PENDING_REVIEW',canonical(observed),tid))
    record(db,tid,'CHANGED_AFTER_PENDING_REVIEW',observed)
    db.execute('COMMIT')
    return {**base,'state':'CHANGED_AFTER_PENDING_REVIEW',
            'observedState':observed['status'],'pendingAttempt':True}
   phase=observed['status']
   db.execute('UPDATE replacements SET phase=?,last_proof=? WHERE trade_id=?',
              (phase,canonical(observed),tid))
   record(db,tid,'READBACK',observed)
   db.execute('COMMIT')
   return {**base,'state':phase,'nextInstruction':STATUSES.get(phase),
           'readbackOnly':True,'stopCoverageCertified':False}
  except Exception as exc:
   db.execute('ROLLBACK')
   return {**base,'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__}
def note_attempt(path,tid,*,step,request_fingerprint):
 """Crash-safe declaration before *external* demo write; never dispatches."""
 with closing(dbopen(path)) as db:
  db.execute('BEGIN IMMEDIATE')
  try:
   row=db.execute('SELECT phase,pending FROM replacements WHERE trade_id=?',(tid,)).fetchone()
   if row is None:raise ValueError('UNKNOWN_TRADE')
   if row['pending'] is not None:raise ValueError('PENDING_OUTCOME_REQUIRES_REVIEW')
   if STATUSES.get(row['phase'])!=step:raise ValueError('STEP_NOT_MATCHING_READBACK')
   if not isinstance(request_fingerprint,str) or len(request_fingerprint)!=64 or any(c not in '0123456789abcdef' for c in request_fingerprint):
    raise ValueError('INVALID_REQUEST_FINGERPRINT')
   pending={'step':step,'before':row['phase'],'fingerprint':request_fingerprint}
   db.execute('UPDATE replacements SET pending=?,phase=? WHERE trade_id=?',
              (canonical(pending),'WRITE_ATTEMPT_RECORDED',tid))
   record(db,tid,'WRITE_ATTEMPT_RECORDED',pending)
   db.execute('COMMIT')
   return {'state':'WRITE_ATTEMPT_RECORDED','canDispatch':False,'canRetry':False}
  except Exception:
   db.execute('ROLLBACK');raise

def confirm_step(path,tid,*,step,request_fingerprint,positions,algos,
                 regular_orders,authenticated_sim_readback=False):
 """Advance a recorded demo attempt only after an exact expected transition.

 No HTTP. In particular, absence of an order is NOT proof of a successful
 POST: a placement must be observed on the exchange by its client ID.
 """
 base={'state':'REVIEW_REQUIRED','canDispatch':False,'canRetry':False,'liveEnabled':False}
 if not authenticated_sim_readback:
  return {**base,'reason':'NO_TRUSTED_SIM_READBACK'}
 with closing(dbopen(path)) as db:
  db.execute('BEGIN IMMEDIATE')
  try:
   row=db.execute('SELECT * FROM replacements WHERE trade_id=?',(tid,)).fetchone()
   if row is None:raise ValueError('UNKNOWN_TRADE')
   if row['pending'] is None:raise ValueError('NO_PENDING_STEP')
   pending=json.loads(row['pending'])
   if pending['step']!=step or pending['fingerprint']!=request_fingerprint:
    raise ValueError('PENDING_FINGERPRINT_MISMATCH')
   if not all(isinstance(x,list) for x in (positions,algos,regular_orders)):
    raise ValueError('INVALID_READBACK')
   bind=json.loads(row['binding'])
   matching=[p for p in positions if isinstance(p,dict) and str(p.get('id'))==bind['positionId']]
   if len(matching)!=1:raise ValueError('POSITION_ID_NOT_PRESENT')
   seen=inspect(position=matching[0],algos=algos,regular_orders=regular_orders,
        expected_position_id=bind['positionId'],
        old_tp_client=bind['old_tp_client'],old_sl_client=bind['old_sl_client'],
        new_tp_client=bind['new_tp_client'],new_sl_client=bind['new_sl_client'])
   expected={
     STEPS[0]:'DUPLICATE_STOPS_REVIEW',
     STEPS[1]:'NEW_STOP_ONLY_OLD_TP_REVIEW',
     STEPS[2]:'NEW_STOP_PRESENT_TP_MISSING',
     STEPS[3]:'PAIR_RESTORED_OFFLINE_ONLY'}
   if seen['status']!=expected.get(step):
    raise ValueError('STEP_OUTCOME_NOT_IN_EXPECTED_STATE')
   # A complete open-order listing is essential: otherwise canceled orders
   # cannot be distinguished from omitted pages.
   if not all(isinstance(x,dict) for x in algos+regular_orders):
    raise ValueError('INVALID_ORDER_ROWS')
   phase=seen['status']
   db.execute('UPDATE replacements SET pending=NULL,phase=?,last_proof=? WHERE trade_id=?',
              (phase,canonical(seen),tid))
   record(db,tid,'CONFIRMED_STEP',{'step':step,'fingerprint':request_fingerprint,
                                  'observed':seen})
   db.execute('COMMIT')
   return {**base,'state':phase,'confirmedByReadback':True,
           'nextInstruction':STATUSES.get(phase),'stopCoverageCertified':False}
  except Exception as exc:
   db.execute('ROLLBACK')
   return {**base,'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__}

def finalize_closed(path,tid,*,positions,algos,regular_orders,
                    authenticated_sim_readback=False):
 """Immutable terminal close proof; never infer 'closed' from missing one page."""
 base={'state':'REVIEW_REQUIRED','canDispatch':False,'canRetry':False}
 if not authenticated_sim_readback or any(not isinstance(x,list) for x in
                                           (positions,algos,regular_orders)):
  return {**base,'reason':'COMPLETE_AUTHENTICATED_READBACK_REQUIRED'}
 if any(not isinstance(x,dict) for rows in (positions,algos,regular_orders) for x in rows):
  return {**base,'reason':'INVALID_ACCOUNT_ROW'}
 with closing(dbopen(path)) as db:
  db.execute('BEGIN IMMEDIATE')
  try:
   row=db.execute('SELECT * FROM replacements WHERE trade_id=?',(tid,)).fetchone()
   if row is None:raise ValueError('UNKNOWN_TRADE')
   bind=json.loads(row['binding'])
   if row['pending'] is not None:raise ValueError('PENDING_WRITE_NOT_RECONCILED')
   if row['phase']=='CLOSED_CONFIRMED':
    db.execute('COMMIT')
    return {'state':'CLOSED_CONFIRMED','alreadyFinal':True,
            'canDispatch':False,'canRetry':False}
   if row['phase']!='PAIR_RESTORED_OFFLINE_ONLY':
    raise ValueError('PAIR_NOT_PREVIOUSLY_VERIFIED')
   if any(str(p.get('id'))==bind['positionId'] or p.get('symbol')==bind['symbol']
          for p in positions):raise ValueError('POSITION_STILL_OBSERVED')
   if any(o.get('symbol')==bind['symbol'] for o in algos+regular_orders):
    raise ValueError('ORDER_STILL_OBSERVED')
   evidence={'positionId':bind['positionId'],'symbol':bind['symbol'],
             'allPositionAndExitOrdersAbsent':True}
   db.execute('UPDATE replacements SET phase=?,last_proof=? WHERE trade_id=?',
              ('CLOSED_CONFIRMED',canonical(evidence),tid))
   record(db,tid,'CLOSED_CONFIRMED',evidence)
   db.execute('COMMIT')
   return {'state':'CLOSED_CONFIRMED','canDispatch':False,'canRetry':False}
  except Exception as e:
   db.execute('ROLLBACK')
   return {**base,'reason':str(e) if isinstance(e,ValueError) else type(e).__name__}
