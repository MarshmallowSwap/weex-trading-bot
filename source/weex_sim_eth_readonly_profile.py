"""Extra authenticated read-only market and configuration inspection for demo."""
import json
from pathlib import Path
from weex_http_guard import sdk_types
from weex_new_sim_domain_readonly import SimReadOnly,HOST
cfg,contract,ops=sdk_types()
cred=json.loads((Path(__file__).resolve().parent/'weex_credentials.json').read_text())
s=SimReadOnly()
paths=('get_capi_v3_market_exchangeInfo','get_capi_v3_market_ticker_bookTicker','get_capi_v3_account_symbolConfig')
s.allowed_extra=frozenset(ops[n]['path'] for n in paths)
import weex_new_sim_domain_readonly as sim
sim.ALLOWED=sim.ALLOWED|s.allowed_extra
try:
 c=contract(config_rest_api=cfg(base_path=HOST,api_key=cred['api_key'],api_secret=cred['secret_key'],passphrase=cred['passphrase'],session=s,timeout=8,max_retries=0))
 for n in paths:
  try:
   r=c.rest_api.execute_operation(n,{'query':{'symbol':'ETHUSDT'} if 'exchangeInfo' not in n else {}})
   data=r.data
   if isinstance(data,list):
    matching=[x for x in data if isinstance(x,dict) and x.get('symbol')=='ETHUSDT']
    print(n,'LIST_COUNT',len(data),'ETH',matching[:1])
   elif isinstance(data,dict):
    if n.endswith('exchangeInfo'):
     print(n,'TOP_KEYS',list(data),'SYMBOLS',next((len(v) for k,v in data.items() if k=='symbols' and isinstance(v,list)),None))
     x=[v for v in data.get('symbols',[]) if v.get('symbol')=='ETHUSDT']
     print('ETH_MARKET_SPEC',x[:1])
    else: print(n,'DATA',data)
   else:print(n,'SHAPE',type(data).__name__)
  except Exception as e: print(n,'ERROR_CLASS',type(e).__name__)
finally:s.close()
