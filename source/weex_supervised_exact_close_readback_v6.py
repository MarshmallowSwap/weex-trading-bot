"""Independent authenticated GET-only finality of an exact supervised reduceOnly close.

ACK != FILLED. Read-only: no retries, no cancellations, no live GO mutation.
Evidence is linked to the real durable UNKNOWN entry and one-shot close intent.
"""
from __future__ import annotations
import json,sqlite3,time
from contextlib import closing
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_supervised_real_recovery_v3 import prove_unknown_intent
from weex_supervised_reduceonly_close_transport_v4 import STATE
ROOT=Path(__file__).resolve().parent
def amount(v):
 try:
  if isinstance(v,bool):return None
  n=D(str(v))
  return n if n.is_finite() and n>0 else None
 except (TypeError,ValueError,InvalidOperation):return None

def classify(entry,close_payload,close_order,exit_fills,stop_history,account,*,close_order_id,now_ms=None):
 """Pure decision using independently fetched exchange evidence."""
 def block(reason):
  return {'status':reason,'verifiedFlat':False,'safeToRetryClose':False,
          'releaseCertified':False,'exchangeWrites':0}
 if any(not isinstance(x,dict) for x in (entry,close_payload,close_order,account)):
  return block('INVALID_READBACK')
 if any(not isinstance(x,list) for x in (exit_fills,stop_history)):
  return block('INCOMPLETE_READBACK')
 qty=amount(entry.get('quantity'))
 if qty is None or entry.get('symbol')!='ETHUSDT' or entry.get('positionSide')!='LONG':
  return block('INVALID_ENTRY')
 if (close_payload.get('symbol')!='ETHUSDT' or close_payload.get('side')!='SELL'
     or close_payload.get('positionSide')!='LONG' or close_payload.get('reduceOnly') is not True
     or amount(close_payload.get('quantity'))!=qty):
  return block('CLOSE_INTENT_MISMATCH')
 if (str(close_order.get('orderId'))!=str(close_order_id)
     or not str(close_order_id).isdigit()
     or close_order.get('symbol')!='ETHUSDT'
     or close_order.get('status')!='FILLED'
     or close_order.get('reduceOnly') is not True
     or close_order.get('positionSide')!='LONG'
     or close_order.get('side')!='SELL'
     or amount(close_order.get('executedQty'))!=qty):
  return block('EXACT_REDUCEONLY_FILL_UNVERIFIED')
 if (not exit_fills or len(exit_fills)>=100 or
     any(not isinstance(x,dict) or str(x.get('orderId'))!=str(close_order_id)
         or x.get('symbol')!='ETHUSDT' or x.get('side')!='SELL'
         or x.get('positionSide')!='LONG' or not str(x.get('id','')).isdigit()
         for x in exit_fills)):
  return block('EXIT_FILLS_UNVERIFIED')
 if (len({str(x['id']) for x in exit_fills})!=len(exit_fills)
     or sum((amount(x.get('qty')) or D(0) for x in exit_fills),D(0))!=qty):
  return block('EXIT_FILL_QUANTITY_MISMATCH')
 expected_stop=str(entry.get('newClientOrderId',''))+'sl'
 stops=[x for x in stop_history if isinstance(x,dict)
        and x.get('clientAlgoId')==expected_stop]
 if (len(stops)!=1 or stops[0].get('algoStatus') not in ('CANCELED','CANCELLED','FILLED')
     or stops[0].get('symbol')!='ETHUSDT' or stops[0].get('reduceOnly') is not True
     or stops[0].get('positionSide')!='LONG' or stops[0].get('side')!='SELL'
     or amount(stops[0].get('quantity'))!=qty):
  return block('STOP_TERMINATION_UNVERIFIED')
 # Exact ETH closure must be flat for ETH, not for unrelated manual assets.
 # A malformed/unattributed exchange row fails closed; never silently omit it.
 from weex_supervised_ownership_scope_v11 import split_exact_symbol
 try:
  scoped=split_exact_symbol(account.get('positions'),account.get('regular'),
                            account.get('conditional'),symbol='ETHUSDT')
 except ValueError:
  return block('ACCOUNT_SNAPSHOT_INVALID')
 if any(scoped[k] for k in ('targetPositions','targetRegular','targetConditional')):
  return block('ACCOUNT_NOT_FLAT')
 return {'status':'EXACT_CLOSE_AND_FLAT_VERIFIED','verifiedFlat':True,
         'safeToRetryClose':False,'releaseCertified':False,'exchangeWrites':0,
         'closeOrderId':str(close_order_id),'stopAlgoId':str(stops[0].get('algoId'))}

def resolve_close_order_id(history,close_payload):
 """Exact immutable client ID lookup after lost ACK; never emits a write."""
 if not isinstance(history,list) or not isinstance(close_payload,dict):
  return None
 cid=close_payload.get('newClientOrderId')
 if not isinstance(cid,str) or not cid.startswith('wxclose_'):
  return None
 rows=[x for x in history if isinstance(x,dict) and x.get('clientOrderId')==cid]
 if len(rows)!=1:
  return None
 x=rows[0]
 if (not str(x.get('orderId','')).isdigit() or
     x.get('symbol')!=close_payload.get('symbol') or
     x.get('side')!=close_payload.get('side') or
     x.get('positionSide')!=close_payload.get('positionSide') or
     x.get('reduceOnly') is not True or
     amount(x.get('origQty'))!=amount(close_payload.get('quantity'))):
  return None
 return str(x['orderId'])

def recover_lost_close_ack(root=ROOT,*,client_id=CLIENT_ID,reader=None):
 """Independent GET history recovery for a durable UNKNOWN close outcome.
 The result is always no-retry and cannot itself certify the live release.
 """
 def blocked(reason):
  return {'status':reason,'verifiedFlat':False,'safeToRetryClose':False,
          'releaseCertified':False,'exchangeWrites':0}
 root=Path(root)
 try:
  import live_control
  if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
   return blocked('PRODUCTION_NOT_STOPPED_OR_INTEGRITY')
  entry=prove_unknown_intent(root/'weex_user_live_lifecycle.sqlite3',client_id)
  db=root/STATE
  with closing(sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)) as c:
   c.execute('PRAGMA query_only=ON')
   rows=c.execute('SELECT payload,status FROM intents WHERE entry=?',(client_id,)).fetchall()
  if len(rows)!=1 or rows[0][1]!='OUTCOME_UNKNOWN':
   return blocked('CLOSE_DURABLE_INTENT_MISSING')
  payload=json.loads(rows[0][0])
  if payload.get('newClientOrderId')!='wxclose_'+client_id.split('_',1)[1]:
   return blocked('CLOSE_CLIENT_ID_INCORRECT')
  from weex_live_worker import Reader
  from weex_execution_readonly import pages
  r=reader if reader is not None else Reader(root)
  current_ms=int(time.time()*1000)
  hist=pages(r.read,'get_capi_v3_order_history',identity='orderId',
             start=0,max_pages=5,symbol='ETHUSDT',
             startTime=current_ms-24*3600*1000,endTime=current_ms)
  oid=resolve_close_order_id(hist,payload)
  if oid is None:return blocked('UNKNOWN_CLOSE_ORDER_IN_HISTORY_NO_RETRY')
  return readback(root,client_id=client_id,close_order_id=oid,reader=r)
 except Exception as exc:
  return {**blocked('CLOSE_HISTORY_READBACK_UNCERTAIN'),'errorType':type(exc).__name__}

def readback(root=ROOT,*,client_id=CLIENT_ID,close_order_id=None,reader=None):
 """Read-only check. Requires known exact close ID, never guesses from flat state."""
 def block(reason):
  return {'status':reason,'verifiedFlat':False,'safeToRetryClose':False,
          'releaseCertified':False,'exchangeWrites':0}
 root=Path(root)
 if not str(close_order_id or '').isdigit():
  return block('EXACT_CLOSE_ORDER_ID_REQUIRED')
 try:
  import live_control
  if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
   return block('PRODUCTION_NOT_STOPPED_OR_INTEGRITY')
  entry=prove_unknown_intent(root/'weex_user_live_lifecycle.sqlite3',client_id)
  db=root/STATE
  with closing(sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)) as c:
   c.execute('PRAGMA query_only=ON')
   rows=c.execute('SELECT payload,status FROM intents WHERE entry=?',(client_id,)).fetchall()
  if len(rows)!=1 or rows[0][1]!='OUTCOME_UNKNOWN':
   return block('CLOSE_DURABLE_INTENT_MISSING')
  close_payload=json.loads(rows[0][0])
  from weex_live_worker import Reader
  r=reader if reader is not None else Reader(root)
  order=r.read('get_capi_v3_order',orderId=str(close_order_id))
  fills=r.read('get_capi_v3_userTrades',symbol='ETHUSDT',orderId=str(close_order_id),limit=100)
  stop_response=r.read('get_capi_v3_allAlgoOrders',symbol='ETHUSDT')
  if not isinstance(stop_response,dict) or not isinstance(stop_response.get('orders'),list):
   return block('STOP_HISTORY_SCHEMA')
  positions,regular,conditional=r.account()
  return classify(entry,close_payload,order,fills,stop_response['orders'],
                  {'positions':positions,'regular':regular,'conditional':conditional},
                  close_order_id=str(close_order_id))
 except Exception as exc:
  return {**block('READBACK_UNCERTAIN'),'errorType':type(exc).__name__}

if __name__=='__main__':
 print(json.dumps({'status':'INDEPENDENT_CLOSE_READBACK_ONLY','exchangeWrites':0,
                   'releaseCertified':False}))
