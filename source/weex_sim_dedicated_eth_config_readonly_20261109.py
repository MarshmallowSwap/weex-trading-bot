"""Dedicated WEEX sim ETH config GET, never uses live credentials."""
import json,requests
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
R=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
class Session:
 def __init__(self):self.s=requests.Session()
 def request(self,method,url,**kw):
  u=urlsplit(url)
  if method!='GET' or u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.path!='/capi/v3/account/symbolConfig' or parse_qs(u.query)!={'symbol':['ETHUSDT']} or kw.get('data') not in (None,'',b'') or kw.get('json') is not None or kw.get('params'):
   raise PermissionError('SIM_ONLY_ETH_CONFIG_GET')
  kw['allow_redirects']=False
  return self.s.request(method,url,**kw)
 def close(self):self.s.close()
def run():
 cred=json.loads((R/'weex_sim_v3_credentials.json').read_text())
 assert cred['environment']=='WEEX_SIM_V3'
 cfg,contract,ops=sdk_types()
 s=Session()
 try:
  client=contract(config_rest_api=cfg(base_path=HOST,
   api_key=cred['api_key'],api_secret=cred['secret_key'],
   passphrase=cred['passphrase'],session=s,max_retries=0,timeout=8))
  rows=client.rest_api.execute_operation('get_capi_v3_account_symbolConfig',{'query':{'symbol':'ETHUSDT'}}).data
  if not isinstance(rows,list) or len(rows)!=1 or rows[0].get('symbol')!='ETHUSDT':raise ValueError('INVALID_CONFIG')
  print(json.dumps({'simHost':HOST,'margin':rows[0].get('marginType'),
   'crossLeverage':rows[0].get('crossLeverage'),
   'isolatedLongLeverage':rows[0].get('isolatedLongLeverage'),
   'isolatedShortLeverage':rows[0].get('isolatedShortLeverage'),
   'writes':0}))
 finally:s.close()
if __name__=='__main__':run()
