"""Independent authenticated WEEX GET-only close reconciliation.

A lost ACK cannot be inferred from a flat account: the durable reservation
stays UNKNOWN and no automatic second close occurs. For known ACK, compare
exact close order, fills, account, and the original stop's terminal history.
"""
from datetime import datetime,timezone
from weex_cross_1x_supervised_executor_20261109 import get_record,reconcile

def check(db,pilot_id,*,reader):
 def blocked(reason):
  return {'status':'INDEPENDENT_READBACK_BLOCKED','reason':reason,
   'canRetry':False,'exchangeWrites':0,'verifiedFlat':False}
 journal=get_record(db,pilot_id)
 if not journal:return blocked('NO_DURABLE_JOURNAL')
 if journal['status']=='OUTCOME_UNKNOWN':
  return blocked('ACK_UNCERTAIN_NO_GUESS_NO_RESEND')
 if journal['status'] not in ('ACK_RECEIVED_NEEDS_READBACK','CLOSED_VERIFIED'):
  return blocked('INVALID_JOURNAL_STATE')
 if journal['status']=='CLOSED_VERIFIED':
  return blocked('ALREADY_RECONCILED_REQUIRES_FRESH_ACCOUNT_SNAPSHOT')
 try:
  import json
  oid=str(json.loads(journal['response'])['orderId'])
  if not oid.isdecimal():return blocked('INVALID_CLOSE_ORDER_ID')
  from weex_execution_readonly import pages
  order=reader.read('get_capi_v3_order',orderId=oid)
  fills=reader.read('get_capi_v3_userTrades',symbol='ETHUSDT',orderId=oid,limit=100)
  if not isinstance(fills,list) or len(fills)>=100:
   return blocked('FILLS_INCOMPLETE')
  positions,regular,conditional=reader.account()
  history=reader.read('get_capi_v3_allAlgoOrders',symbol='ETHUSDT')
  if not isinstance(history,dict) or history.get('hasMore') is not False:
   return blocked('STOP_HISTORY_TRUNCATED_OR_UNKNOWN')
  if not isinstance(history.get('orders'),list):
   return blocked('STOP_HISTORY_INVALID')
  if not (isinstance(positions,list) and isinstance(regular,list)
          and isinstance(conditional,list)):
   return blocked('ACCOUNT_INCOMPLETE')
  result=reconcile(db,pilot_id=pilot_id,order=order,fills=fills,
    positions=positions,regular_orders=regular,conditional=conditional,
    terminal_stop_history=history['orders'],read_complete=True)
  return {'status':result['state'],'verifiedFlat':result['verifiedFlat'],
    'canRetry':False,'exchangeWrites':0,
    'observedAt':datetime.now(timezone.utc).isoformat(),
    'independentReadback':True}
 except Exception as exc:
  return blocked('READBACK_ERROR_'+type(exc).__name__)
