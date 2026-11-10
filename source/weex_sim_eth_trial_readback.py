"""Authenticated exact demo trial readback, never orders or cancels."""
import json,requests
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
ROOT=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
OPS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
 'get_capi_v3_openAlgoOrders','get_capi_v3_order',
 'get_capi_v3_userTrades','get_capi_v3_allAlgoOrders')
class DemoRead:
 def __init__(self,allowed,oid):self.s=requests.Session();self.allowed=allowed;self.oid=oid
 def request(self,method,url,**kw):
  u=urlsplit(url)
  q=parse_qs(u.query)
  if (method!='GET' or u.scheme!='https' or u.netloc!='api-sim.weex.com'
      or u.path not in self.allowed or u.fragment or kw.get('params') or kw.get('json') is not None
      or kw.get('data') not in (None,'',b'')):
   raise PermissionError('NOT_SIM_GET')
  if q and not (q=={'symbol':['ETHUSDT']} or q=={'orderId':[self.oid]} or
               q=={'symbol':['ETHUSDT'],'orderId':[self.oid],'limit':['100']}):
   raise PermissionError('UNEXPECTED_SIM_QUERY')
  kw['allow_redirects']=False
  r=self.s.request(method,url,**kw)
  if 300<=r.status_code<400:raise PermissionError('REDIRECT')
  return r
 def close(self):self.s.close()
def run():
 cfg,contract,ops=sdk_types();trial=json.loads((ROOT/'weex_sim_eth_trial_one_shot.json').read_text())
 oid=trial.get('exchangeOrderId')
 if not oid:raise ValueError('SIM_ORDER_ID_NOT_KNOWN')
 creds=json.loads((ROOT/'weex_credentials.json').read_text())
 s=DemoRead({ops[n]['path'] for n in OPS},oid)
 out={'host':HOST,'orderId':oid,'stage':'READBACK','errors':{},'exchangeWrites':0}
 try:
  c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
      api_secret=creds['secret_key'],passphrase=creds['passphrase'],session=s,
      timeout=8,max_retries=0))
  queries={'get_capi_v3_order':{'orderId':oid},
   'get_capi_v3_userTrades':{'symbol':'ETHUSDT','orderId':oid,'limit':100},
   'get_capi_v3_allAlgoOrders':{'symbol':'ETHUSDT'},
   'get_capi_v3_openAlgoOrders':{'symbol':'ETHUSDT'}}
  for n in OPS:
   try:
    rows=c.rest_api.execute_operation(n,{'query':queries.get(n,{})}).data
    out[n]=rows
   except Exception as e:out['errors'][n]=type(e).__name__
 finally:s.close()
 (ROOT/'weex_sim_eth_trial_readback_latest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
 for n in OPS:
  x=out.get(n)
  if isinstance(x,list):
   print(n,'COUNT',len(x),'DATA',x[:2] if n in ('get_capi_v3_account_position_allPosition','get_capi_v3_openAlgoOrders') else '')
  elif isinstance(x,dict):print(n,'DATA',x)
  else: print(n,'ERR',out['errors'].get(n))
if __name__=='__main__':run()
