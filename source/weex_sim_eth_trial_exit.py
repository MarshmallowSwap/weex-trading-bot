"""WEEX API-SIM ONLY: exact stop cancel then exact positionId close.
One DELETE + one POST maximum, both persisted before sending. GET reconciliation.
No contact with production domain. Must be exclusively the documented trial.
"""
import json,os,requests
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from datetime import datetime,timezone
from weex_http_guard import sdk_types
from weex_pilot_emergency_close_sdk import exact_position_sdk_fields
ROOT=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
REPORT=ROOT/'weex_sim_eth_trial_exit.json'
OPS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
     'get_capi_v3_openAlgoOrders','get_capi_v3_allAlgoOrders')
class SimExact:
 def __init__(self,allow):
  self.allow=allow;self.s=requests.Session();self.armed=None;self.used=set()
 def request(self,method,url,**kw):
  u=urlsplit(url);q=parse_qs(u.query)
  if (u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment
      or kw.get('params') or kw.get('json') is not None):
   raise PermissionError('NON_SIM_DESTINATION')
  if method=='GET':
   if u.path not in self.allow or kw.get('data') not in (None,'',b''):
    raise PermissionError('SIM_READ_NOT_ALLOWED')
   if q and (q!={'symbol':['ETHUSDT']} or u.path not in
      ('/capi/v3/openAlgoOrders','/capi/v3/allAlgoOrders')):
    raise PermissionError('SIM_GET_QUERY_UNEXPECTED')
  elif method=='DELETE':
   if (u.path!='/capi/v3/algoOrder' or q!={'orderId':[self.cancel_id]}
       or self.armed!='cancel' or 'cancel' in self.used
       or kw.get('data') not in (None,'',b'')):
    raise PermissionError('SIM_EXACT_CANCEL_DENIED')
   self.used.add('cancel');self.armed=None
  elif method=='POST':
   if (u.path!='/capi/v3/closePositions' or u.query or self.armed!='close'
       or 'close' in self.used or json.loads(kw.get('data') or b'{}')!=self.close_payload):
    raise PermissionError('SIM_EXACT_POSITION_CLOSE_DENIED')
   self.used.add('close');self.armed=None
  else:raise PermissionError('SIM_UNSUPPORTED_WRITE')
  kw['allow_redirects']=False
  r=self.s.request(method,url,**kw)
  if 300<=r.status_code<400:raise PermissionError('SIM_REDIRECT')
  return r
 def close(self):self.s.close()
def save(r):
 t=REPORT.with_suffix('.tmp');t.write_text(json.dumps(r,indent=2));os.replace(t,REPORT)
def run():
 if REPORT.exists():print('TRIAL_EXIT_ALREADY_RESERVED_NO_REPEAT');return
 trial=json.loads((ROOT/'weex_sim_eth_trial_one_shot.json').read_text())
 pre=json.loads((ROOT/'weex_sim_eth_trial_readback_latest.json').read_text())
 oid=str(trial.get('exchangeOrderId',''))
 p=pre.get('get_capi_v3_account_position_allPosition')
 a=pre.get('get_capi_v3_openAlgoOrders')
 entry=pre.get('get_capi_v3_order')
 if not (isinstance(p,list) and len(p)==1 and isinstance(a,list) and len(a)==1
   and isinstance(entry,dict)):raise PermissionError('READBACK_MISSING')
 pos=p[0];stop=a[0];sid=str(stop['algoId']);pid=str(pos['id'])
 if (entry.get('status')!='FILLED' or str(entry.get('orderId'))!=oid or
   entry.get('clientOrderId')!=trial['clientOrderId'] or
   pos.get('symbol')!='ETHUSDT' or pos.get('side')!='LONG' or pos.get('marginType')!='ISOLATED'
   or pos.get('leverage')!='1' or pos.get('size')!='0.002'
   or stop.get('symbol')!='ETHUSDT' or stop.get('positionSide')!='LONG'
   or stop.get('reduceOnly') is not True or stop.get('orderType')!='STOP_MARKET'
   or stop.get('algoStatus')!='UNTRIGGERED'
   or stop.get('clientAlgoId')!=trial['clientOrderId']+'sl'
   or str(stop.get('actualOrderId'))!=oid
   or str(stop.get('triggerPrice'))!=trial['stopPrice']):
  raise PermissionError('EXACT_DEMO_ENTRY_STOP_OWNERSHIP_FAILED')
 cfg,contract,ops=sdk_types()
 allowed={ops[n]['path'] for n in OPS}
 creds=json.loads((ROOT/'weex_credentials.json').read_text())
 s=SimExact(allowed)
 r={'host':HOST,'trial':trial['clientOrderId'],'positionId':pid,
    'stopAlgoId':sid,'stage':'BEFORE_CANCEL','productionWrites':0,
    'simCancelRequests':0,'simCloseRequests':0,'flatVerified':False}
 save(r)
 try:
  with exact_position_sdk_fields():
   c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
     api_secret=creds['secret_key'],passphrase=creds['passphrase'],
     session=s,max_retries=0,timeout=8))
   def read(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
   def account():
    return (read('get_capi_v3_account_position_allPosition'),
      read('get_capi_v3_openOrders'),read('get_capi_v3_openAlgoOrders'))
   positions,regular,algos=account()
   if not (len(positions)==1 and not regular and len(algos)==1
      and str(positions[0].get('id'))==pid and str(algos[0].get('algoId'))==sid):
    raise PermissionError('SIM_ACCOUNT_CHANGED_BEFORE_CANCEL')
   s.cancel_id=sid;s.armed='cancel'
   r['stage']='CANCEL_INTENT_RESERVED';save(r)
   try:
    response=c.rest_api.execute_operation('delete_capi_v3_algoOrder',{'query':{'orderId':sid}})
    r['simCancelRequests']=1;r['cancelHttpStatus']=response.status_code
    r['stage']='CANCEL_ACK_READBACK_REQUIRED'
   except Exception as e:
    r['stage']='CANCEL_OUTCOME_UNKNOWN';r['cancelErrorClass']=type(e).__name__
    save(r);print(json.dumps(r));return
   save(r)
   positions,regular,algos=account()
   r['stopAbsentFromOpen']=isinstance(algos,list) and not algos
   r['positionAfterCancel']=len(positions) if isinstance(positions,list) else 'unknown'
   r['stage']='CANCEL_REOBSERVED'
   save(r)
   # Even if terminal history is unavailable, the demo-only position
   # is now unprotected: close by exact positionId after fresh no-stop read.
   if not (isinstance(positions,list) and len(positions)==1 and
      str(positions[0].get('id'))==pid and
      isinstance(regular,list) and not regular and
      isinstance(algos,list) and not algos):
    raise PermissionError('SIM_NOT_SAFE_TO_CLOSE_OR_ALREADY_CHANGED')
   payload={'symbol':'ETHUSDT','positionId':int(pid)}
   s.close_payload=payload;s.armed='close'
   r['stage']='EXACT_POSITION_CLOSE_INTENT_RESERVED';save(r)
   try:
    response=c.rest_api.execute_operation('post_capi_v3_closePositions',{'body':payload})
    r['simCloseRequests']=1;r['closeHttpStatus']=response.status_code
    r['closeResponseShape']=type(response.data).__name__
    if isinstance(response.data,list) and response.data:
     r['closeResponseSuccess']=response.data[0].get('success')
     r['closeOrderId']=str(response.data[0].get('successOrderId',''))
    r['stage']='CLOSE_ACK_READBACK_REQUIRED'
   except Exception as e:
    r['stage']='CLOSE_OUTCOME_UNKNOWN';r['closeErrorClass']=type(e).__name__
    save(r);print(json.dumps(r));return
   save(r)
   positions,regular,algos=account()
   r['positionCount']=len(positions) if isinstance(positions,list) else 'unknown'
   r['regularCount']=len(regular) if isinstance(regular,list) else 'unknown'
   r['algoCount']=len(algos) if isinstance(algos,list) else 'unknown'
   r['flatVerified']=positions==[] and regular==[] and algos==[]
   r['stage']='SIM_CYCLE_FLAT_VERIFIED' if r['flatVerified'] else 'SIM_CYCLE_NOT_FLAT'
   save(r)
 except Exception as e:
  r['errorClass']=type(e).__name__;r['stage']='EXIT_INTERRUPTED_NEEDS_SIM_GET_RECONCILIATION'
  save(r)
 finally:s.close()
 print(json.dumps(r))
if __name__=='__main__':run()
