"""Exactly-once dedicated WEEX SIM ETH CROSS 1x account setup.
Uses dedicated SIM credentials and only api-sim.weex.com; no trade entries.
"""
import json,os,requests
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
import live_control
R=Path(__file__).resolve().parent;HOST='https://api-sim.weex.com'
STATE=R/'weex_sim_cross_1x_setup_20261109.json'
GETS=('get_capi_v3_account_symbolConfig','get_capi_v3_account_position_allPosition',
'get_capi_v3_openOrders','get_capi_v3_openAlgoOrders')
class Scope:
 def __init__(self,ops):
  self.s=requests.Session();self.paths={ops[x]['path'] for x in GETS};self.next_write=None
 def request(self,method,url,**kw):
  u=urlsplit(url)
  if (u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment or
     kw.get('params') or kw.get('json') is not None):
   raise PermissionError('SIM_ONLY_DOMAIN')
  if method=='GET':
   if u.path not in self.paths or kw.get('data') not in (None,'',b'') or (
    u.query and (u.path!='/capi/v3/account/symbolConfig' or parse_qs(u.query)!={'symbol':['ETHUSDT']})):
    raise PermissionError('SIM_GET_NOT_SCOPED')
  elif method=='POST':
   if u.query or u.path!=self.next_write:raise PermissionError('SIM_WRITE_NOT_RESERVED')
   data=json.loads(kw.get('data') or b'{}')
   expected=({'symbol':'ETHUSDT','marginType':'CROSS','separatedType':'COMBINED'}
    if u.path=='/capi/v3/account/marginType' else
    {'symbol':'ETHUSDT','marginType':'CROSS','crossLeverage':'1'})
   if data!=expected:raise PermissionError('SIM_CONFIG_BODY_MISMATCH')
   self.next_write=None
  else:raise PermissionError('INVALID_METHOD')
  kw['allow_redirects']=False
  result=self.s.request(method,url,**kw)
  if not 200<=result.status_code<300:raise RuntimeError('SIM_HTTP_NON_SUCCESS')
  return result
 def close(self):self.s.close()
def save(data):
 tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');os.replace(tmp,STATE)
def run():
 if live_control.state(R)['mode']!='STOPPED' or live_control.build_errors(R):
  raise PermissionError('PRODUCTION_NOT_STOPPED')
 if STATE.exists():
  print(json.dumps({'status':'EXISTING_JOURNAL_NO_RETRY','writes':0}));return
 credentials=json.loads((R/'weex_sim_v3_credentials.json').read_text(encoding='utf-8'))
 if credentials.get('environment')!='WEEX_SIM_V3':raise PermissionError('DEDICATED_SIM_CREDENTIALS_REQUIRED')
 cfg,Contract,ops=sdk_types();s=Scope(ops)
 record={'at':datetime.now(timezone.utc).isoformat(),'host':HOST,'stage':'PREPARING',
  'productionWrites':0,'configurationWritesReserved':0,'entryWrites':0}
 save(record)
 try:
  c=Contract(config_rest_api=cfg(base_path=HOST,api_key=credentials['api_key'],
    api_secret=credentials['secret_key'],passphrase=credentials['passphrase'],
    session=s,timeout=8,max_retries=0))
  def read(op,q=None):return c.rest_api.execute_operation(op,{'query':q or {}}).data
  for op in GETS[1:]:
   v=read(op)
   if v!=[]:raise PermissionError('SIM_ACCOUNT_NOT_FLAT_'+op)
  def conf():
   v=read('get_capi_v3_account_symbolConfig',{'symbol':'ETHUSDT'})
   if not isinstance(v,list) or len(v)!=1:return None
   return v[0]
  current=conf()
  if current is None:raise PermissionError('CONFIG_MISSING')
  record['initialMargin']=current.get('marginType')
  if current.get('marginType') not in ('CROSS','CROSSED'):
   body={'symbol':'ETHUSDT','marginType':'CROSS','separatedType':'COMBINED'}
   record.update(stage='MARGIN_POST_OUTCOME_UNKNOWN',configurationWritesReserved=1)
   save(record);s.next_write='/capi/v3/account/marginType'
   try:c.rest_api.execute_operation('post_capi_v3_account_marginType',{'body':body})
   except Exception as ex:
    record['errorClass']=type(ex).__name__;save(record);print(json.dumps(record));return
   record.update(stage='MARGIN_ACK_NEEDS_READBACK',marginPostObserved=True);save(record)
   current=conf()
   if current is None or current.get('marginType') not in ('CROSS','CROSSED'):
    raise PermissionError('MARGIN_READBACK_INCOMPLETE')
  if str(current.get('crossLeverage'))!='1':
   body={'symbol':'ETHUSDT','marginType':'CROSS','crossLeverage':'1'}
   record.update(stage='LEVERAGE_POST_OUTCOME_UNKNOWN',configurationWritesReserved=record['configurationWritesReserved']+1)
   save(record);s.next_write='/capi/v3/account/leverage'
   try:c.rest_api.execute_operation('post_capi_v3_account_leverage',{'body':body})
   except Exception as ex:
    record['errorClass']=type(ex).__name__;save(record);print(json.dumps(record));return
   record.update(stage='LEVERAGE_ACK_NEEDS_READBACK',leveragePostObserved=True);save(record)
  current=conf()
  if (current is None or current.get('marginType') not in ('CROSS','CROSSED')
   or str(current.get('crossLeverage'))!='1' or current.get('separatedType')!='COMBINED'):
   raise PermissionError('FINAL_SIM_CROSS_1X_READBACK_FAILED')
  record.update(stage='SIM_CROSS_1X_CONFIRMED',margin=current.get('marginType'),
   crossLeverage=str(current.get('crossLeverage')),productionWrites=0)
  save(record)
 except Exception as exc:
  record['stage']='SIM_CONFIGURATION_REVIEW_REQUIRED';record['errorClass']=type(exc).__name__
  save(record)
 finally:s.close()
 print(json.dumps(record))
if __name__=='__main__':run()
