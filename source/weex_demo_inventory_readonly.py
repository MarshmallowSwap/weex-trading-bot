"""Read-only WEEX futures demo inventory, redacted safe summary.

Queries modern api-sim.weex.com futures endpoints and legacy
api-contract.weex.com/capi/v3/sim/* demo-only endpoints.
Does not call non-demo private endpoints on production.
No balance amount, position contents, identity, credentials or raw responses printed.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from pathlib import Path
P=Path(__file__).with_name('weex_sim_v3_credentials.json')
TARGETS=(
 ('SIM_V3_BALANCE','api-sim.weex.com','/capi/v3/account/balance'),
 ('SIM_V3_POSITIONS','api-sim.weex.com','/capi/v3/account/position/allPosition'),
 ('SIM_V3_OPEN_ORDERS','api-sim.weex.com','/capi/v3/openOrders'),
 ('SIM_V3_OPEN_ALGOS','api-sim.weex.com','/capi/v3/openAlgoOrders'),
 ('LEGACY_DEMO_BALANCE','api-contract.weex.com','/capi/v3/sim/balance'),
 ('LEGACY_DEMO_POSITIONS','api-contract.weex.com','/capi/v3/sim/position/allPosition'),
 ('LEGACY_DEMO_HISTORY','api-contract.weex.com','/capi/v3/sim/order/history'),
)
def probe():
 c=json.loads(P.read_text(encoding='utf-8-sig'))
 if c.get('environment')!='WEEX_SIM_V3':raise ValueError('INVALID_ENV_TAG')
 rows={}
 for label,host,path in TARGETS:
  ts=str(int(time.time()*1000))
  signature=base64.b64encode(hmac.new(c['secret_key'].encode(),(ts+'GET'+path).encode(),hashlib.sha256).digest()).decode()
  request=urllib.request.Request('https://'+host+path,method='GET',headers={
    'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':signature,
    'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':ts,
    'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(request,timeout=8) as response:
    http=response.status; data=json.load(response)
  except urllib.error.HTTPError as e:
   http=e.code
   try:data=json.loads(e.read(2048))
   except (ValueError,TypeError):data=None
  except Exception as e:
   rows[label]={'status':'NETWORK_ERROR','errorType':type(e).__name__}
   continue
  row={'httpStatus':http,'jsonType':type(data).__name__}
  if isinstance(data,list):
   row['rowCount']=len(data)
   row['rowShapeValid']=all(isinstance(x,dict) for x in data)
   if 'BALANCE' in label:
    row['assetCodes']=sorted({str(x.get('asset')) for x in data if isinstance(x,dict) and isinstance(x.get('asset'),str)})
  elif isinstance(data,dict):
   code=data.get('code')
   if isinstance(code,(int,str)) and str(code).lstrip('-').isdigit():row['businessCode']=int(code)
   inner=data.get('data')
   row['dataType']=type(inner).__name__ if inner is not None else 'missing'
   if isinstance(inner,list):
    row['rowCount']=len(inner)
    if 'BALANCE' in label:
     row['assetCodes']=sorted({str(x.get('asset')) for x in inner if isinstance(x,dict) and isinstance(x.get('asset'),str)})
  rows[label]=row
  time.sleep(.3)
 return {'readOnly':True,'ordersSubmitted':False,'livePrivateEndpointsQueried':False,'results':rows}
if __name__=='__main__':
 print(json.dumps(probe(),ensure_ascii=False))
