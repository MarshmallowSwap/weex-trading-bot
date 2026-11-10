"""Read-only adoption of a manually MOVED TP for a bot-owned position.

Only a uniquely observed, full-size, active, reduce-only TAKE_PROFIT_MARKET
bound to the exact bot position can be accepted. An original TP that is no
longer visible must be independently verified CANCELLED/EXPIRED in complete
history before recognizing its replacement. Same-algo repricing is accepted
only when the exact original ID remains active.

No TP placement, deletion, automatic price restoration or trade authorization.
"""
import hashlib,json
from decimal import Decimal,InvalidOperation

def num(x):
 try:
  v=Decimal(str(x))
  if not v.is_finite() or v<=0:raise ValueError('NOT_POSITIVE')
  return v
 except (InvalidOperation,ValueError,TypeError):
  raise ValueError('INVALID_QUANTITY_OR_PRICE')

def evaluate(item,writes,rows,history,observed_at,now_ms):
 if (not isinstance(item,dict) or not isinstance(writes,dict)
     or not isinstance(rows,(tuple,list)) or len(rows)!=3
     or not all(isinstance(g,list) and all(isinstance(x,dict) for x in g) for g in rows)
     or not isinstance(observed_at,int) or not 0<=now_ms-observed_at<=5000):
  raise ValueError('INVALID_OR_STALE_ACCOUNT_SNAPSHOT')
 if item.get('state') not in ('PROTECTED','REVIEW_REQUIRED','TP_PENDING'):
  raise ValueError('NOT_ACTIVE_TP_LIFECYCLE')
 plan=item['plan'];owned=item['owned']
 if not isinstance(owned,dict) or plan.get('entrySource')=='manual_telegram':
  raise ValueError('BOT_POSITION_OWNERSHIP_REQUIRED')
 entry=writes.get('ENTRY') or {};tp_write=writes.get('TP') or {}
 if (entry.get('state')!='RESPONSE_RECEIVED' or
     tp_write.get('state')!='RESPONSE_RECEIVED'):
  raise ValueError('BOT_ENTRY_TP_ACK_REQUIRED')
 ack=tp_write.get('response')
 if isinstance(ack,list):ack=ack[0] if len(ack)==1 else None
 if not isinstance(ack,dict) or ack.get('success') is not True or not ack.get('orderId'):
  raise ValueError('BOT_TP_ACK_NOT_VERIFIED')
 old_id=str(ack['orderId'])
 entry_ack=entry.get('response')
 if isinstance(entry_ack,list):entry_ack=entry_ack[0] if len(entry_ack)==1 else None
 if (not isinstance(entry_ack,dict) or entry_ack.get('success') is not True
     or str(entry_ack.get('orderId'))!=str(owned.get('entryOrderId'))):
  raise ValueError('ENTRY_ACK_MISMATCH')
 p,regular,algos=rows
 own=[x for x in p if x.get('symbol')==item['symbol']]
 if len(own)!=1:raise ValueError('POSITION_NOT_UNIQUE')
 pos=own[0];tp=owned.get('tpRequest') or {}
 qty=num(pos.get('size'))
 if (str(pos.get('id'))!=str(owned.get('positionId'))
     or pos.get('side')!=plan['entry']['positionSide']
     or qty!=num(owned['quantity'])):
  raise ValueError('POSITION_OWNERSHIP_OR_QUANTITY_CHANGED')
 if any(x.get('symbol')==item['symbol'] for x in regular):
  raise ValueError('OTHER_REGULAR_ORDER_PRESENT')
 match=[a for a in algos if a.get('symbol')==item['symbol']]
 if len(match)!=1:raise ValueError('TP_MISSING_OR_AMBIGUOUS')
 new=match[0]
 if (not new.get('algoId') or new.get('orderType')!='TAKE_PROFIT_MARKET'
    or new.get('algoStatus') not in ('NEW','UNTRIGGERED')
    or new.get('positionSide')!=pos['side']
    or new.get('side')!=('SELL' if pos['side']=='LONG' else 'BUY')
    or new.get('reduceOnly') is not True
    or new.get('workingType') not in ('MARK_PRICE','CONTRACT_PRICE')
    or num(new.get('quantity'))!=qty or num(new.get('triggerPrice'))<=0):
  raise ValueError('REPLACEMENT_TP_NOT_FULL_CLOSING')
 # Price can be moved anywhere by the user; do not pretend it still meets
 # the original +15 USDT target. Preserve manual intent, including loss exits.
 new_id=str(new['algoId'])
 if new_id!=old_id:
  if (not isinstance(history,dict) or history.get('hasMore') is not False
      or not isinstance(history.get('orders'),list)):
   raise ValueError('HISTORICAL_TP_NOT_COMPLETE')
  old=[a for a in history['orders'] if str(a.get('algoId'))==old_id]
  if len(old)!=1 or old[0].get('algoStatus') not in ('CANCELED','CANCELLED','EXPIRED'):
   raise ValueError('ORIGINAL_TP_NOT_CONFIRMED_CANCELED')
  if (old[0].get('clientAlgoId')!=tp.get('clientAlgoId')
      or old[0].get('symbol')!=item['symbol']
      or old[0].get('positionSide')!=pos['side']):
   raise ValueError('ORIGINAL_TP_IDENTITY_CHANGED')
 else:
  if new.get('clientAlgoId')!=tp.get('clientAlgoId'):
   raise ValueError('SAME_ORDER_ID_CLIENT_CHANGED')
 if new_id==old_id and num(new['triggerPrice'])==num(tp['triggerPrice']):
  raise ValueError('NO_MANUAL_TP_CHANGE')
 proof={'schema':'BOT_TP_MANUALLY_MOVED_V1','tradeId':item['id'],
   'symbol':item['symbol'],'positionId':str(pos['id']),
   'entryOrderId':str(owned['entryOrderId']),
   'originalTpId':old_id,'observedTpId':new_id,
   'quantity':str(qty),'observedTriggerPrice':str(new['triggerPrice']),
   'workingType':new['workingType'],'observedAtMs':observed_at,
   'status':'MANUAL_TP_ADOPTED_FOR_MONITORING','botTpPriceNoLongerEnforced':True,
   'netTargetStillGuaranteed':False,'maySendOrders':False,
   'mayCancelOrReplaceTp':False}
 proof['sha256']=hashlib.sha256(json.dumps(proof,sort_keys=True).encode()).hexdigest()
 return proof
