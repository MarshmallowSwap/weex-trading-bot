"""Production WEEX authenticated GET recovery verifier for an unknown one-shot entry.

No exchange writes, no entry retries, no credentials embedded, no gate mutation.
Use only after a one-shot executor has durably committed an exact client ID.
Returns NEED_CLOSE only if exchange entry and stop are independently proven.
"""
from __future__ import annotations
import json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
# Real recovery uses the production wxentry_ namespace, not the old wxpilot_ validator.

SYMBOL='ETHUSDT'
SOURCE='https://api-contract.weex.com'
class RecoveryBlocked(RuntimeError):pass

def count(value):
 try:
  if isinstance(value,bool):return None
  n=D(str(value))
  return n if n.is_finite() and n>0 else None
 except (InvalidOperation,TypeError,ValueError):return None

def single_exact_order(order_rows,client_id,entry):
 if not isinstance(order_rows,list):raise RecoveryBlocked('ORDER_HISTORY_INVALID')
 matched=[x for x in order_rows if x.get('clientOrderId')==client_id]
 if len(matched)!=1:raise RecoveryBlocked('ORDER_ACK_AMBIGUOUS_OR_MISSING')
 order=matched[0]
 if (order.get('symbol')!=SYMBOL or order.get('status')!='FILLED'
    or order.get('positionSide')!=entry.get('positionSide')
    or order.get('side')!=entry.get('side')
    or count(order.get('executedQty'))!=count(entry.get('quantity'))
    or not str(order.get('orderId','')).isdigit()):
  raise RecoveryBlocked('ENTRY_NOT_EXACT_FULL_FILL')
 return order

def exact_attached_stop(entry,order,stop_orders):
 if not isinstance(stop_orders,list) or len(stop_orders)!=1:
  raise RecoveryBlocked('EXACTLY_ONE_ATTACHED_STOP_REQUIRED')
 stop=stop_orders[0];cid=entry['newClientOrderId'];oid=str(order['orderId'])
 if (not isinstance(stop,dict) or stop.get('clientAlgoId')!=cid+'sl'
     or str(stop.get('actualOrderId'))!=oid
     or stop.get('symbol')!=SYMBOL or stop.get('positionSide')!='LONG'
     or stop.get('side')!='SELL' or stop.get('reduceOnly') is not True
     or stop.get('orderType') not in ('STOP_MARKET','STOP_LOSS_MARKET')
     or stop.get('algoStatus') not in ('NEW','UNTRIGGERED')
     or stop.get('workingType')!='MARK_PRICE'
     or count(stop.get('quantity'))!=count(entry['quantity'])
     or count(stop.get('triggerPrice'))!=count(entry['slTriggerPrice'])
     or not str(stop.get('algoId','')).isdigit()):
  raise RecoveryBlocked('ATTACHED_STOP_IDENTITY_OR_FIELDS_NOT_VERIFIED')
 return {'verified':True,'algoId':str(stop['algoId']),
         'triggerPrice':str(count(stop['triggerPrice']))}

def classify(*,entry,history,stop_orders,positions,regular_orders,conditional_orders):
 """Classify actual readbacks; never infer a stop from an HTTP entry ACK."""
 if not isinstance(entry,dict) or not entry.get('newClientOrderId','').startswith('wxentry_'):
  raise RecoveryBlocked('INVALID_JOURNALED_ENTRY')
 if entry.get('symbol')!=SYMBOL or entry.get('SlWorkingType')!='MARK_PRICE' or not count(entry.get('slTriggerPrice')):
  raise RecoveryBlocked('ATOMIC_MARK_STOP_NOT_IN_JOURNAL')
 if any(not isinstance(x,list) for x in (history,stop_orders,positions,regular_orders,conditional_orders)):
  raise RecoveryBlocked('INCOMPLETE_EXCHANGE_READBACK')
 order=single_exact_order(history,entry['newClientOrderId'],entry)
 stop=exact_attached_stop(entry,order,stop_orders)
 matching_positions=[p for p in positions if p.get('symbol')==SYMBOL and count(p.get('size'))]
 if len(matching_positions)!=1:raise RecoveryBlocked('EXACT_OPEN_POSITION_NOT_PROVEN')
 position=matching_positions[0]
 if (position.get('side')!=entry['positionSide']
     or count(position.get('size'))!=count(entry['quantity'])
     or not str(position.get('id','')).isdigit()):
  raise RecoveryBlocked('POSITION_SIZE_SIDE_OR_ID_MISMATCH')
 if any(x.get('symbol')==SYMBOL for x in regular_orders):
  raise RecoveryBlocked('UNEXPECTED_REGULAR_ORDERS')
 if len([x for x in conditional_orders if x.get('symbol')==SYMBOL])!=1:
  raise RecoveryBlocked('UNEXPECTED_ADDITIONAL_CONDITIONAL_ORDERS')
 return {'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':entry['newClientOrderId'],
  'entryOrderId':str(order['orderId']),'stopAlgoId':stop['algoId'],
  'positionId':str(position['id']),'symbol':SYMBOL,'quantity':str(count(entry['quantity'])),
  'stopTriggerPrice':stop['triggerPrice'],'entryRetriesAllowed':False,
  'closeAuthorized':False,'exchangeWrites':0}

def prove_unknown_intent(db_path,client_id):
 """Consult production durable journal in read-only mode; never manufacture it."""
 path=Path(db_path)
 if not path.is_file():raise RecoveryBlocked('PRODUCTION_JOURNAL_MISSING')
 with closing(sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)) as c:
  c.row_factory=sqlite3.Row
  c.execute('PRAGMA query_only=ON')
  trade=c.execute('SELECT plan FROM trades_v1 WHERE id=?',(client_id,)).fetchone()
  writes=c.execute("SELECT operation,payload,state,response FROM writes_v1 WHERE trade_id=? AND kind='ENTRY'",(client_id,)).fetchall()
 if not trade or len(writes)!=1:raise RecoveryBlocked('PRODUCTION_DURABLE_INTENT_NOT_FOUND')
 w=writes[0]
 if w['state']!='UNKNOWN' or w['response'] is not None or w['operation']!='post_capi_v3_order':
  raise RecoveryBlocked('NOT_UNKNOWN_PRE_ACK_WORKER_INTENT')
 entry=json.loads(w['payload'])
 plan=json.loads(trade['plan'])
 if plan.get('entry')!=entry or entry.get('newClientOrderId')!=client_id:
  raise RecoveryBlocked('IMMUTABLE_ENTRY_MISMATCH')
 return entry

def read_exchange(client_id,root=None,reader=None):
 from weex_live_worker import Reader
 root=Path(root) if root else Path(__file__).resolve().parent
 entry=prove_unknown_intent(root/'weex_user_live_lifecycle.sqlite3',client_id)
 r=reader if reader is not None else Reader(root)
 # SDK supports orderId only. Resolve a unique client ID from bounded
 # order history, then verify the order with its exchange-assigned ID.
 from weex_execution_readonly import pages
 import time
 now_ms=int(time.time()*1000)
 history=pages(r.read,'get_capi_v3_order_history',identity='orderId',start=0,
   max_pages=5,symbol=SYMBOL,startTime=now_ms-24*3600*1000,endTime=now_ms)
 matches=[x for x in history if x.get('clientOrderId')==client_id]
 if len(matches)!=1:raise RecoveryBlocked('HISTORY_CLIENT_ID_MISSING_OR_AMBIGUOUS')
 exact=r.read('get_capi_v3_order',orderId=matches[0]['orderId'])
 if (not isinstance(exact,dict) or exact.get('clientOrderId')!=client_id
     or str(exact.get('orderId'))!=str(matches[0]['orderId'])):
  raise RecoveryBlocked('EXACT_ORDER_LOOKUP_FAILED')
 stop_result=r.read('get_capi_v3_allAlgoOrders',symbol=SYMBOL)
 stop_orders=stop_result.get('orders',[]) if isinstance(stop_result,dict) else None
 positions,regular,conditional=r.account()
 order_id=exact.get('orderId')
 if not order_id:raise RecoveryBlocked('EXCHANGE_ORDER_ID_MISSING')
 linked=[x for x in stop_orders or [] if str(x.get('actualOrderId'))==str(order_id)]
 return classify(entry=entry,history=[exact],stop_orders=linked,
  positions=positions,regular_orders=regular,conditional_orders=conditional)

if __name__=='__main__':
 # Safe default: always report readiness, never inspect private account unrequested.
 print(json.dumps({'status':'REAL_GET_RECOVERY_MODULE_READY','hasWriteTransport':False,
   'entrySubmissionEnabled':False,'closeSubmissionEnabled':False,
   'liveReleaseCertified':False}))
