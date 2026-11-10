"""Supervised ETHUSDT CROSS 1x emergency-close orchestration.

An exact-position close may be sent ONCE by an injected, separately authorized
transport. This module does not construct a live exchange transport, store API
secrets, arm the bot, or expose a production-send CLI. Durable UNKNOWN is NEVER
retried; an ACK is not proof of closure.
"""
import json,sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
from weex_cross_1x_emergency_readiness_20261109 import assess

def stamp():return datetime.now(timezone.utc).isoformat()
@contextmanager
def db_connect(path):
 c=sqlite3.connect(str(path),timeout=8,isolation_level=None)
 try:
  c.execute('PRAGMA busy_timeout=8000')
  c.execute('PRAGMA synchronous=FULL')
  c.execute('PRAGMA journal_mode=DELETE')
  c.execute('''CREATE TABLE IF NOT EXISTS supervised_cross_close_v1(
   pilot_id TEXT PRIMARY KEY, position_id TEXT UNIQUE NOT NULL,
   entry_order_id TEXT UNIQUE NOT NULL, stop_algo_id TEXT NOT NULL,
   payload TEXT NOT NULL, expected_qty TEXT NOT NULL, status TEXT NOT NULL,
   created_at TEXT NOT NULL, response TEXT, checked_at TEXT)''')
  yield c
 finally:
  c.close()
def get_record(db,pilot_id):
 with db_connect(db) as c:
  c.row_factory=sqlite3.Row
  r=c.execute('SELECT * FROM supervised_cross_close_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
  return dict(r) if r else None

def dispatch(db,*,pilot_id,intent,entry,positions,regular_orders,conditional,
             exchange_cross_leverage,approval,transport,main_bot_stopped,
             account_read_complete=True):
 """One-shot execution hook. Callers must supply fresh independent data.

 The transport MUST be injected: no production transport is assembled here.
 """
 if not main_bot_stopped:raise PermissionError('MAIN_BOT_NOT_STOPPED')
 if not isinstance(pilot_id,str) or not pilot_id.startswith('wxpilot_') or len(pilot_id)>100:
  raise PermissionError('INVALID_PILOT_ID')
 if not isinstance(intent,dict) or pilot_id!=intent.get('newClientOrderId'):
  raise PermissionError('PILOT_JOURNAL_IDENTITY_MISMATCH')
 if not callable(approval) or not callable(transport):
  raise PermissionError('INDEPENDENT_APPROVAL_AND_TRANSPORT_REQUIRED')
 evidence=assess(intent=intent,entry=entry,positions=positions,
  regular_orders=regular_orders,conditional=conditional,
  exchange_cross_leverage=exchange_cross_leverage,
  account_read_complete=account_read_complete,
  main_bot_stopped=main_bot_stopped)
 if evidence['readyForSupervisedClose'] is not True:
  raise PermissionError('CROSS_1X_PREVIEW_DENIED:'+evidence['reason'])
 payload=evidence['closePayloadPreview']
 # Approval is scoped to this exact pilot, order and position. The caller
 # must verify a fresh explicit operator decision; absence is a hard denial.
 if approval({'pilotId':pilot_id,'entryOrderId':evidence['entryOrderId'],
             'positionId':evidence['positionId'],
             'stopAlgoId':evidence['stopAlgoId'],
             'payload':payload}) is not True:
  raise PermissionError('EXACT_CLOSE_OPERATOR_APPROVAL_MISSING')
 db=Path(db)
 with db_connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  r=c.execute('SELECT status FROM supervised_cross_close_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
  if r:
   c.rollback()
   return {'state':'ALREADY_RESERVED_NO_RETRY','prior':r[0],'canRetry':False}
  other=c.execute('SELECT pilot_id FROM supervised_cross_close_v1 WHERE position_id=? OR entry_order_id=?',
     (evidence['positionId'],evidence['entryOrderId'])).fetchone()
  if other:
   c.rollback()
   return {'state':'OTHER_RESERVATION_NO_RETRY','canRetry':False}
  c.execute('''INSERT INTO supervised_cross_close_v1
   (pilot_id,position_id,entry_order_id,stop_algo_id,payload,expected_qty,status,created_at)
   VALUES (?,?,?,?,?,?,?,?)''',
   (pilot_id,evidence['positionId'],evidence['entryOrderId'],
    evidence['stopAlgoId'],json.dumps(payload,sort_keys=True),
    str(intent['quantity']),'OUTCOME_UNKNOWN',stamp()))
  c.commit()
 try:
  result=transport('post_capi_v3_closePositions',payload)
 except Exception:
  return {'state':'OUTCOME_UNKNOWN','canRetry':False,'verifiedFlat':False}
 if (not isinstance(result,dict) or result.get('success') is not True
     or not result.get('orderId')
     or str(result.get('positionId'))!=evidence['positionId']):
  return {'state':'OUTCOME_UNKNOWN','canRetry':False,'verifiedFlat':False}
 with db_connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  c.execute('''UPDATE supervised_cross_close_v1 SET
   status='ACK_RECEIVED_NEEDS_READBACK', response=?, checked_at=?
   WHERE pilot_id=? AND status='OUTCOME_UNKNOWN' ''',
   (json.dumps({'orderId':str(result['orderId'])}),stamp(),pilot_id))
  c.commit()
 return {'state':'ACK_RECEIVED_NEEDS_READBACK','canRetry':False,
         'verifiedFlat':False,'closeOrderId':str(result['orderId'])}

def reconcile(db,*,pilot_id,order,fills,positions,regular_orders,conditional,
              terminal_stop_history,read_complete=True):
 """Offline assessment of independently supplied exchange GET evidence.

 A missing ACK remains unresolved; never infer a specific close order from
 a flat account. This is intentionally stricter than best-effort recovery.
 """
 def deny(reason):
  return {'state':reason,'verifiedFlat':False,'canRetry':False}
 rec=get_record(db,pilot_id)
 if rec is None:return deny('NO_DURABLE_CLOSE_RESERVATION')
 if rec['status']=='CLOSED_VERIFIED':
  return {'state':'ALREADY_CLOSED_VERIFIED','verifiedFlat':True,'canRetry':False}
 if not read_complete or not all(isinstance(x,list) for x in
     (fills,positions,regular_orders,conditional,terminal_stop_history)):
  return deny('INCOMPLETE_EXCHANGE_READBACK')
 if rec['status']!='ACK_RECEIVED_NEEDS_READBACK' or not rec['response']:
  return deny('OUTCOME_UNKNOWN_NO_ACK_NO_RETRY')
 if not isinstance(order,dict) or any(not isinstance(x,dict) for x in
     fills+positions+regular_orders+conditional+terminal_stop_history):
  return deny('INVALID_EXCHANGE_READBACK')
 from decimal import Decimal,InvalidOperation
 try:
  ack=json.loads(rec['response'])
  exact=json.loads(rec['payload'])
  oid=str(ack['orderId'])
  stop=[x for x in terminal_stop_history if str(x.get('algoId'))==rec['stop_algo_id']]
  ids=[str(x['id']) for x in fills]
  qty=Decimal(str(order['executedQty']))
  filled=sum((Decimal(str(x['qty'])) for x in fills),Decimal('0'))
  valid=(len(stop)==1 and stop[0].get('algoStatus') in ('CANCELED','CANCELLED')
    and len(fills)>0 and len(set(ids))==len(ids) and qty>0
    and qty==filled==Decimal(str(rec['expected_qty']))
    and not positions and not regular_orders and not conditional
    and exact=={'symbol':'ETHUSDT','positionId':int(rec['position_id'])}
    and str(order.get('orderId'))==oid and order.get('symbol')=='ETHUSDT'
    and order.get('positionSide')=='LONG' and order.get('side')=='SELL'
    and order.get('status')=='FILLED' and order.get('reduceOnly') is True
    and all(str(x.get('orderId'))==oid and x.get('symbol')=='ETHUSDT'
       and x.get('side')=='SELL' and x.get('positionSide')=='LONG' for x in fills))
 except (KeyError,ValueError,TypeError,InvalidOperation,ArithmeticError):
  valid=False
 if not valid:return deny('CLOSE_EVIDENCE_NOT_SUFFICIENT')
 with db_connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  c.execute('''UPDATE supervised_cross_close_v1 SET status='CLOSED_VERIFIED',
   checked_at=? WHERE pilot_id=? AND status='ACK_RECEIVED_NEEDS_READBACK' ''',
   (stamp(),pilot_id))
  c.commit()
 return {'state':'CLOSED_VERIFIED','verifiedFlat':True,'canRetry':False,
         'orderId':oid,'positionId':rec['position_id']}
