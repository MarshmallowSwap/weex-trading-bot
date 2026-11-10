"""One-shot SIMULATION-ONLY account setup for isolated 1x ETHUSDT.
Will NEVER target live host. Refuses any non-flat simulated account.
No trading orders submitted.
"""
import json,requests
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime,timezone
from weex_http_guard import sdk_types
ROOT=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
READ={'/capi/v3/account/symbolConfig','/capi/v3/account/position/allPosition',
      '/capi/v3/openOrders','/capi/v3/openAlgoOrders'}
MARGIN='/capi/v3/account/marginType'
LEVERAGE='/capi/v3/account/leverage'
class ExactSim:
 def __init__(self):self.session=requests.Session();self.allowed_write=None
 def request(self,method,url,**kw):
  u=urlsplit(url)
  from urllib.parse import parse_qs
  if (u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment
      or kw.get('params') or kw.get('json') is not None):
   raise PermissionError('SIMULATION_HOST_OR_REQUEST_INVALID')
  if u.query and not (method=='GET' and u.path=='/capi/v3/account/symbolConfig'
                      and parse_qs(u.query)=={'symbol':['ETHUSDT']}):
   raise PermissionError('UNEXPECTED_SIM_QUERY')
  body=kw.get('data')
  if method=='GET':
   if u.path not in READ or body not in (None,b'',''):
    raise PermissionError('UNEXPECTED_SIM_GET')
  elif method=='POST':
   if u.path!=self.allowed_write:raise PermissionError('SIM_WRITE_NOT_ARMED')
   expected=({ 'symbol':'ETHUSDT','marginType':'ISOLATED','separatedType':'COMBINED' }
     if u.path==MARGIN else {'symbol':'ETHUSDT','marginType':'ISOLATED',
       'isolatedLongLeverage':'1','isolatedShortLeverage':'1'})
   if json.loads(body or b'{}')!=expected:raise PermissionError('SIM_PAYLOAD_NOT_EXACT')
   self.allowed_write=None  # one-shot
  else:raise PermissionError('NO_DELETE_OR_NON_SIM_REQUEST')
  kw['allow_redirects']=False
  r=self.session.request(method,url,**kw)
  if 300<=r.status_code<400:raise PermissionError('REDIRECT_REJECTED')
  return r
 def close(self):self.session.close()
def run():
 cfg,contract,ops=sdk_types();creds=json.loads((ROOT/'weex_credentials.json').read_text())
 s=ExactSim();out={'checkedAt':datetime.now(timezone.utc).isoformat(),'simHost':HOST,
   'accountOnly':True,'tradingOrdersSubmitted':0,'steps':[],'finished':False}
 try:
  c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
   api_secret=creds['secret_key'],passphrase=creds['passphrase'],
   session=s,timeout=8,max_retries=0))
  def op(name,query=None,body=None):
   args={'query':query or {}} if body is None else {'body':body}
   return c.rest_api.execute_operation(name,args).data
  for n in ('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders','get_capi_v3_openAlgoOrders'):
   x=op(n)
   if not isinstance(x,list) or x:raise PermissionError('SIM_ACCOUNT_NOT_FLAT_OR_INCOMPLETE:'+n)
  x=op('get_capi_v3_account_symbolConfig',query={'symbol':'ETHUSDT'})
  if not isinstance(x,list) or len(x)!=1 or x[0].get('symbol')!='ETHUSDT':
   raise PermissionError('SIM_ETH_CONFIG_UNAVAILABLE')
  out['before']={k:x[0].get(k) for k in ('marginType','isolatedLongLeverage','isolatedShortLeverage')}
  if x[0]['marginType']!='ISOLATED':
   s.allowed_write=MARGIN
   op('post_capi_v3_account_marginType',body={'symbol':'ETHUSDT',
      'marginType':'ISOLATED','separatedType':'COMBINED'})
   out['steps'].append('SIM_MARGIN_CHANGE_ACK')
   y=op('get_capi_v3_account_symbolConfig',query={'symbol':'ETHUSDT'})
   if len(y)!=1 or y[0].get('marginType')!='ISOLATED':
    raise PermissionError('SIM_MARGIN_READBACK_FAILED')
  s.allowed_write=LEVERAGE
  op('post_capi_v3_account_leverage',body={'symbol':'ETHUSDT',
      'marginType':'ISOLATED','isolatedLongLeverage':'1','isolatedShortLeverage':'1'})
  out['steps'].append('SIM_LEVERAGE_CHANGE_ACK')
  y=op('get_capi_v3_account_symbolConfig',query={'symbol':'ETHUSDT'})
  if not isinstance(y,list) or len(y)!=1:raise PermissionError('SIM_CONFIG_READBACK_MISSING')
  out['after']={k:y[0].get(k) for k in ('marginType','isolatedLongLeverage','isolatedShortLeverage')}
  if out['after']['marginType']!='ISOLATED' or any(
      str(out['after'][k]) not in ('1','1.0','1.00') for k in ('isolatedLongLeverage','isolatedShortLeverage')):
   raise PermissionError('SIM_NOT_ISOLATED_1X')
  out['finished']=True
 except Exception as e:
  out['errorClass']=type(e).__name__;out['errorSummary']=str(e)[:100]
 finally:
  s.close()
  (ROOT/'weex_sim_eth_isolated_1x_latest.json').write_text(json.dumps(out,indent=2))
  print(json.dumps(out))
if __name__=='__main__':run()
