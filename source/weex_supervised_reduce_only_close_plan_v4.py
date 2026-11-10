"""Strict WEEX MARKET reduceOnly close request planning; no network or sending.

Official WEEX /capi/v3/order accepts reduceOnly on MARKET orders.
All independent account and position evidence must be verified first.
"""
from decimal import Decimal as D,InvalidOperation
from weex_http_guard import prepare_sdk_request
from weex_supervised_crash_executor_v2 import CLIENT_ID
class ClosePlanBlocked(ValueError):pass

def compose(*,proof,positions,regular_orders,conditional_orders,settings):
 if not isinstance(proof,dict) or proof.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE':
  raise ClosePlanBlocked('PROVEN_ENTRY_AND_ATTACHED_STOP_REQUIRED')
 if (proof.get('clientOrderId')!=CLIENT_ID or proof.get('symbol')!='ETHUSDT'
    or str(proof.get('quantity')) not in ('0.001','0.0010','0.00100')):
  raise ClosePlanBlocked('PILOT_ID_OR_EXACT_QUANTITY_MISMATCH')
 from weex_supervised_ownership_scope_v11 import split_exact_symbol
 try:
  scope=split_exact_symbol(positions,regular_orders,conditional_orders)
 except ValueError as exc:
  raise ClosePlanBlocked('ACCOUNT_SCOPE_READBACK_INVALID') from exc
 target_positions=scope['targetPositions']
 target_orders=scope['targetRegular']
 target_conditional=scope['targetConditional']
 if len(target_positions)!=1 or target_orders or len(target_conditional)!=1:
  raise ClosePlanBlocked('TARGET_SYMBOL_UNEXPECTED_EXPOSURE')
 if (not isinstance(settings,list) or len(settings)!=1
     or settings[0].get('symbol')!='ETHUSDT'
     or settings[0].get('marginType') not in ('CROSS','CROSSED')
     or str(settings[0].get('crossLeverage'))!='100'):
  raise ClosePlanBlocked('CROSS_100X_NOT_CONFIRMED')
 p=target_positions[0];stop=target_conditional[0]
 if (str(p.get('id'))!=str(proof.get('positionId')) or
    p.get('symbol')!='ETHUSDT' or p.get('side')!='LONG' or
    D(str(p.get('size','0')))!=D('0.001') or
    str(stop.get('algoId'))!=str(proof.get('stopAlgoId')) or
    stop.get('symbol')!='ETHUSDT' or stop.get('reduceOnly') is not True):
  raise ClosePlanBlocked('EXACT_POSITION_OR_PROTECTIVE_STOP_CHANGED')
 payload={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
     'type':'MARKET','quantity':'0.001',
     'newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
     'reduceOnly':True}
 preflight=prepare_sdk_request('post_capi_v3_order',payload)
 if preflight.get('state')!='STOPPED_BEFORE_NETWORK' or preflight.get('networkRequests')!=0:
  raise ClosePlanBlocked('SDK_PREVIEW_NOT_VERIFIED')
 return {'status':'CLOSE_PREVIEW_ONLY','payload':payload,
   'referencePositionId':str(p['id']),'referenceStopAlgoId':str(stop['algoId']),
   'networkRequests':0,'exchangeWrites':0,'liveDispatchEnabled':False,
   'exchangeOutcomeCertified':False}

if __name__=='__main__':
 print({'status':'CLOSE_REDUCE_ONLY_PREVIEW_COMPONENT_READY','liveDispatchEnabled':False})
