"""One-shot pilot emergency-exit dispatcher, hardware/network isolated.

Accepts only a simulation gateway. Persists the no-resend reservation before
calling the gateway; never grants production order permission. A live WEEX
executor must have a separate, reviewed authority and independent exit test.
"""
import json
from pathlib import Path
from decimal import Decimal,InvalidOperation
from weex_isolated_pilot_transport_harness import simulate_dispatch
from weex_isolated_pilot_offline_journal import connect
from contextlib import closing
from weex_http_guard import prepare_sdk_request

REQUIRED={'symbol','side','positionSide','type','quantity','reduceOnly','newClientOrderId'}

def validated_close_payload(p):
 if not isinstance(p,dict) or set(p)!=REQUIRED:
  raise ValueError('CLOSE_FIELDS_INVALID')
 if p['symbol']!='ETHUSDT' or p['type']!='MARKET' or p['reduceOnly'] is not True:
  raise ValueError('NOT_EXACT_REDUCE_ONLY_MARKET')
 if p['positionSide'] not in ('LONG','SHORT'):
  raise ValueError('INVALID_POSITION_SIDE')
 if p['side']!=('SELL' if p['positionSide']=='LONG' else 'BUY'):
  raise ValueError('WRONG_CLOSE_DIRECTION')
 q=Decimal(str(p['quantity']))
 if not q.is_finite() or q<=0 or q>Decimal('.01'):
  raise ValueError('INVALID_CLOSE_QUANTITY')
 if not isinstance(p['newClientOrderId'],str) or not p['newClientOrderId'].startswith('wxpilot_'):
  raise ValueError('UNSCOPED_CLIENT_ID')
 return p

def simulate_close_once(db,pilot_id,gateway,*,production_mode='STOPPED'):
 if production_mode!='STOPPED':raise PermissionError('MAIN_BOT_NOT_STOPPED')
 if gateway is None or getattr(gateway,'simulation_only',False) is not True:
  raise PermissionError('SIMULATION_GATEWAY_REQUIRED')
 with closing(connect(db)) as c:
  row=c.execute('SELECT state,proposals,close_id FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
  if row is None:return {'state':'UNKNOWN_PILOT','realOrdersSent':0}
  state,raw,cid=row
  try:payload=validated_close_payload(json.loads(raw)['close'])
  except (ValueError,TypeError,KeyError,InvalidOperation) as e:
   return {'state':'CLOSE_PLAN_INVALID','reason':type(e).__name__,'realOrdersSent':0}
  if payload['newClientOrderId']!=cid:
   return {'state':'CLOSE_CLIENT_ID_MISMATCH','realOrdersSent':0}
  # Exact official SDK serialization: it must stop before any network call.
  preview=prepare_sdk_request('post_capi_v3_order',payload)
  if preview['networkRequests']!=0 or preview['state']!='STOPPED_BEFORE_NETWORK':
   raise PermissionError('OFFLINE_SERIALIZER_UNSAFE')
  result=simulate_dispatch(db,pilot_id,'close',gateway)
  return {'state':result['state'],'realOrdersSent':0,
          'canRetry':False,'mainStrategyUnchanged':True}
