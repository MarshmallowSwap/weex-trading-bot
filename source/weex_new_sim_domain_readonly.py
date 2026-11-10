"""New WEEX standalone simulation domain: authenticated GET-only availability probe.
Every request is pinned to https://api-sim.weex.com. No production reads or writes.
"""
import json,requests
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
from weex_http_guard import sdk_types
ROOT=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
OPS=('get_capi_v3_account_balance','get_capi_v3_account_position_allPosition',
     'get_capi_v3_openOrders','get_capi_v3_openAlgoOrders')
class SimReadOnly:
 def __init__(self):
  self.session=requests.Session()
 def request(self,method,url,**kw):
  u=urlsplit(url)
  if method!='GET' or u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment:
   raise PermissionError('ONLY_AUTHENTICATED_SIM_GET_PERMITTED')
  if u.path not in ALLOWED:
   raise PermissionError('SIM_GET_PATH_NOT_ALLOWLISTED')
  if kw.get('data') not in (None,'',b'') or kw.get('json') is not None:
   raise PermissionError('SIM_GET_MUST_NOT_HAVE_BODY')
  kw['allow_redirects']=False
  resp=self.session.request(method,url,**kw)
  if 300<=resp.status_code<400:raise PermissionError('SIM_REDIRECT_DENIED')
  return resp
 def close(self):self.session.close()
_,_,all_ops=sdk_types()
ALLOWED=frozenset(all_ops[x]['path'] for x in OPS)
def run():
 cfg,contract,ops=sdk_types()
 cred=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
 session=SimReadOnly()
 results={}
 try:
  c=contract(config_rest_api=cfg(base_path=HOST,
   api_key=cred['api_key'],api_secret=cred['secret_key'],
   passphrase=cred['passphrase'],session=session,timeout=8,max_retries=0))
  for name in OPS:
   try:
    r=c.rest_api.execute_operation(name,{'query':{}})
    data=r.data
    results[name]={'ok':r.status_code==200 and isinstance(data,list),
                   'shape':'list' if isinstance(data,list) else type(data).__name__,
                   'rows':len(data) if isinstance(data,list) else None}
    if name=='get_capi_v3_account_balance' and isinstance(data,list):
     results[name]['assets']=sorted(set(str(x.get('asset')) for x in data if isinstance(x,dict)))
   except Exception as e:results[name]={'ok':False,'errorClass':type(e).__name__}
 finally:session.close()
 out={'checkedAt':datetime.now(timezone.utc).isoformat(),'host':HOST,
      'mode':'AUTHENTICATED_SIM_GET_ONLY','results':results,
      'simConfirmed':all(x['ok'] for x in results.values()),'exchangeWrites':0}
 (ROOT/'weex_new_sim_domain_readonly_latest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
 print(json.dumps(out))
if __name__=='__main__':run()
