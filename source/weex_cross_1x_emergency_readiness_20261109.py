"""Read-only authorization assessment for a supervised WEEX ETH CROSS 1x emergency exit.

Only produces an exact-position CLOSE preview. Never dispatches orders.
Requires fresh, unambiguous WEEX position and native stop readback.
"""
from decimal import Decimal,InvalidOperation
from weex_pilot_emergency_close_sdk import exact_payload,preview_position_close

def n(value):
 try:
  x=Decimal(str(value))
  return x if x.is_finite() and x>=0 else None
 except (InvalidOperation,ValueError,TypeError):
  return None

def assess(*,intent,entry,positions,regular_orders,conditional,exchange_cross_leverage,
           account_read_complete=True,main_bot_stopped=True):
 def fail(reason):
  return {'readyForSupervisedClose':False,'reason':reason,
          'maySendOrder':False,'previewOnly':True,'exchangeWrites':0}
 if not (main_bot_stopped is True and account_read_complete is True):
  return fail('BOT_OR_ACCOUNT_SAFETY_NOT_CONFIRMED')
 if not all(isinstance(v,list) for v in (positions,regular_orders,conditional)):
  return fail('ACCOUNT_SNAPSHOT_INCOMPLETE')
 if any(not isinstance(x,dict) for x in positions+regular_orders+conditional):
  return fail('INVALID_ACCOUNT_ROWS')
 if not isinstance(intent,dict) or not isinstance(entry,dict):
  return fail('MISSING_DURABLE_INTENT_OR_ORDER')
 if (intent.get('symbol')!='ETHUSDT' or intent.get('side')!='BUY'
     or intent.get('positionSide')!='LONG' or intent.get('type')!='MARKET'
     or not isinstance(intent.get('newClientOrderId'),str)
     or not intent['newClientOrderId'].startswith('wxpilot_')
     or entry.get('clientOrderId')!=intent['newClientOrderId']
     or entry.get('symbol')!='ETHUSDT' or entry.get('positionSide')!='LONG'
     or entry.get('status')!='FILLED'):
  return fail('ENTRY_INTENT_AND_EXCHANGE_ORDER_NOT_IDENTICAL')
 qty=n(intent.get('quantity'))
 if (qty is None or qty<=0 or qty>Decimal('.01')
     or n(entry.get('executedQty'))!=qty
     or n(entry.get('avgPrice')) is None or n(entry.get('avgPrice'))<=0
     or qty*n(entry.get('avgPrice'))>Decimal('5')
     or not entry.get('orderId')
     or str(exchange_cross_leverage)!='1'):
  return fail('CROSS_1X_QUANTITY_UNVERIFIED')
 if regular_orders or len(positions)!=1 or len(conditional)!=1:
  return fail('ACCOUNT_NOT_UNAMBIGUOUS')
 pos=positions[0];stop=conditional[0]
 if (pos.get('symbol')!='ETHUSDT' or pos.get('side')!='LONG'
     or pos.get('marginType')!='CROSSED' or pos.get('separatedMode')!='COMBINED'
     or str(pos.get('leverage'))!='1' or n(pos.get('size'))!=qty):
  return fail('POSITION_NOT_EXACT_CROSS_1X')
 if (stop.get('symbol')!='ETHUSDT' or stop.get('positionSide')!='LONG'
     or stop.get('side')!='SELL' or stop.get('reduceOnly') is not True
     or stop.get('algoStatus') not in ('NEW','UNTRIGGERED')
     or stop.get('orderType') not in ('STOP_MARKET','STOP_LOSS_MARKET')
     or stop.get('workingType')!='MARK_PRICE'
     or not stop.get('algoId')
     or n(stop.get('triggerPrice')) is None or n(stop.get('triggerPrice'))<=0
     or n(stop.get('triggerPrice'))>=n(entry.get('avgPrice'))
     or n(stop.get('quantity'))!=qty
     or stop.get('clientAlgoId')!=intent['newClientOrderId']+'sl'
     or str(stop.get('actualOrderId'))!=str(entry.get('orderId'))):
  return fail('NATIVE_STOP_NOT_VERIFIED')
 try:
  payload=exact_payload(pos.get('id'))
  preview_position_close(payload)
 except Exception:
  return fail('EXACT_POSITION_CLOSE_SDK_PREVIEW_FAILED')
 return {'readyForSupervisedClose':True,
   'reason':'EXACT_CROSS_1X_POSITION_WITH_NATIVE_STOP_CORROBORATED',
   'positionId':str(pos['id']),
   'entryOrderId':str(entry['orderId']),
   'stopAlgoId':str(stop.get('algoId')),
   'closePayloadPreview':payload,'maySendOrder':False,
   'previewOnly':True,'exchangeWrites':0}
