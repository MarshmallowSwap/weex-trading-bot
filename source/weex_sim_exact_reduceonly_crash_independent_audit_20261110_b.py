"""Independent authenticated GET-only proof of 2026-11-09 active-stop demo."""
import json,os,requests
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from decimal import Decimal as D
from weex_http_guard import sdk_types
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
trial=json.loads((R/'weex_sim_exact_reduceonly_crash_recovery_20261110_b.json').read_text())
if trial.get('stage')!='SIM_CRASH_RECOVERY_FLAT_VERIFIED' or trial.get('host')!=HOST:
 raise PermissionError('DEMO_TRIAL_NOT_COMPLETE')
if live_control.state(R)['mode']!='STOPPED':raise PermissionError('PRODUCTION_RUNNING')
names=['get_capi_v3_order','get_capi_v3_userTrades','get_capi_v3_account_position_allPosition',
       'get_capi_v3_openOrders','get_capi_v3_openAlgoOrders','get_capi_v3_allAlgoOrders']
cfg,contract,ops=sdk_types()
class GetOnly:
 def __init__(self):self.s=requests.Session();self.allowed={ops[n]['path'] for n in names}
 def request(self,method,url,**kw):
  u=urlsplit(url);q=parse_qs(u.query)
  if method!='GET' or u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.path not in self.allowed or u.fragment or kw.get('data') not in (None,'',b''):
   raise PermissionError('GET_ONLY_EXACT_SIM_HOST')
  if q and not (q=={'symbol':['ETHUSDT']} or
     u.path=='/capi/v3/order' and set(q)=={'orderId'} or
     u.path=='/capi/v3/userTrades' and q.get('symbol')==['ETHUSDT'] and q.get('limit')==['100'] and set(q)=={'symbol','orderId','limit'}):
   raise PermissionError('QUERY_DENIED')
  kw['allow_redirects']=False
  return self.s.request(method,url,**kw)
 def close(self):self.s.close()
s=GetOnly()
creds=json.loads((R/'weex_sim_v3_credentials.json').read_text());assert creds.get('environment')=='WEEX_SIM_V3'
c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
  api_secret=creds['secret_key'],passphrase=creds['passphrase'],session=s,
  timeout=8,max_retries=0))
def get(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
report={'checkedAt':datetime.now(timezone.utc).isoformat(),'host':HOST,
 'entryOrderId':trial['entryOrderId'],'closeOrderId':trial['closeOrderId'],
 'stopAlgoId':trial['stopAlgoId'],'productionWrites':0,'demoWrites':0}
try:
 entry=get('get_capi_v3_order',{'orderId':trial['entryOrderId']})
 close=get('get_capi_v3_order',{'orderId':trial['closeOrderId']})
 fills=get('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':trial['closeOrderId'],'limit':100})
 p=get('get_capi_v3_account_position_allPosition')
 o=get('get_capi_v3_openOrders')
 a=get('get_capi_v3_openAlgoOrders')
 hist=get('get_capi_v3_allAlgoOrders',{'symbol':'ETHUSDT'})
 qty=D('0.002')
 report['entryMatched']=(isinstance(entry,dict) and str(entry.get('orderId'))==trial['entryOrderId'] and
    entry.get('clientOrderId')==trial['clientOrderId'] and entry.get('status')=='FILLED')
 report['closeMatched']=(isinstance(close,dict) and str(close.get('orderId'))==trial['closeOrderId'] and
    close.get('reduceOnly') is True and close.get('status')=='FILLED' and
    close.get('symbol')=='ETHUSDT' and close.get('positionSide')=='LONG' and
    D(str(close.get('executedQty','0')))==qty)
 report['closeFillsMatched']=(isinstance(fills,list) and len(fills)>0 and
    sum((D(str(x['qty'])) for x in fills),D(0))==qty and
    all(str(x.get('orderId'))==trial['closeOrderId'] for x in fills))
 report['accountFlat']=p==[] and o==[] and a==[]
 report['openPositions']=len(p) if isinstance(p,list) else None
 report['openOrders']=len(o) if isinstance(o,list) else None
 report['openAlgos']=len(a) if isinstance(a,list) else None
 report['stopFoundInHistory']=any(str(x.get('algoId'))==trial['stopAlgoId']
     for x in hist.get('orders',[]) if isinstance(x,dict)) if isinstance(hist,dict) else False
 report['stopHistoricalStatuses']=[x.get('algoStatus') for x in hist.get('orders',[])
      if isinstance(x,dict) and str(x.get('algoId'))==trial['stopAlgoId']] if isinstance(hist,dict) else []
 report['independentProofPass']=all(report.get(k) is True for k in
   ('entryMatched','closeMatched','closeFillsMatched','accountFlat','stopFoundInHistory'))
except Exception as e:
 report['errorClass']=type(e).__name__
finally:s.close()
p=R/'weex_sim_exact_reduceonly_crash_independent_audit_20261110_b.json'
tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));os.replace(tmp,p)
print(json.dumps(report))
