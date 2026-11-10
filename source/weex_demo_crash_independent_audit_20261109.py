"""GET-only independent audit of controlled demo OS crash and recovery."""
import json,os,requests
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
import live_control
R=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
source=json.loads((R/'weex_demo_crash_recovery_20261109_result.json').read_text())
assert source['status']=='DEMO_CRASH_RECOVERY_PASS' and source['host']==HOST
assert live_control.state(R)['mode']=='STOPPED'
creds=json.loads((R/'weex_sim_v3_credentials.json').read_text());assert creds['environment']=='WEEX_SIM_V3'
cfg,contract,ops=sdk_types()
NAMES=('get_capi_v3_order','get_capi_v3_order_history','get_capi_v3_userTrades',
'get_capi_v3_account_position_allPosition','get_capi_v3_openOrders','get_capi_v3_openAlgoOrders','get_capi_v3_allAlgoOrders')
class GetOnly:
 def __init__(self):self.s=requests.Session();self.paths={ops[n]['path'] for n in NAMES}
 def request(self,method,url,**kw):
  u=urlsplit(url);q=parse_qs(u.query)
  if method!='GET' or u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.path not in self.paths or kw.get('data') not in (None,'',b'') or kw.get('json') is not None or u.fragment:raise PermissionError('DEMO_ONLY_GET')
  if q and not (q=={'symbol':['ETHUSDT']} or u.path=='/capi/v3/order' and set(q)=={'orderId'} or u.path=='/capi/v3/userTrades' and set(q)=={'symbol','orderId','limit'} and q.get('symbol')==['ETHUSDT'] and q.get('limit')==['100']):raise PermissionError('QUERY_DENIED')
  kw['allow_redirects']=False;resp=self.s.request(method,url,**kw)
  if resp.status_code//100!=2:raise RuntimeError('NON_SUCCESS_DEMO_HTTP')
  return resp
 def close(self):self.s.close()
s=GetOnly()
c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],api_secret=creds['secret_key'],passphrase=creds['passphrase'],session=s,timeout=8,max_retries=0))
def get(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
out={'checkedAt':datetime.now(timezone.utc).isoformat(),'host':HOST,'productionWrites':0,'demoWrites':0,'auditType':'INDEPENDENT_DEMO_GET_ONLY'}
try:
 entry=get('get_capi_v3_order',{'orderId':source['entryOrderId']})
 close=get('get_capi_v3_order',{'orderId':source['closeOrderId']})
 fills=get('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':source['closeOrderId'],'limit':100})
 hist=get('get_capi_v3_order_history',{'symbol':'ETHUSDT'})
 p=get('get_capi_v3_account_position_allPosition');o=get('get_capi_v3_openOrders');a=get('get_capi_v3_openAlgoOrders')
 algos=get('get_capi_v3_allAlgoOrders',{'symbol':'ETHUSDT'})
 orders=hist.get('orders',[]) if isinstance(hist,dict) else hist if isinstance(hist,list) else []
 matched=[x for x in orders if isinstance(x,dict) and x.get('clientOrderId')==source['clientOrderId']]
 stops=[x for x in algos.get('orders',[]) if isinstance(x,dict) and x.get('clientAlgoId')==source['clientOrderId']+'sl'] if isinstance(algos,dict) else []
 out['entryExact']=isinstance(entry,dict) and str(entry.get('orderId'))==source['entryOrderId'] and entry.get('clientOrderId')==source['clientOrderId'] and entry.get('status')=='FILLED'
 out['oneEntryOnly']=len(matched)==1
 out['closeExact']=isinstance(close,dict) and str(close.get('orderId'))==source['closeOrderId'] and close.get('status')=='FILLED' and close.get('reduceOnly') is True and D(str(close.get('executedQty','0')))==D('0.002')
 out['closeFillExact']=isinstance(fills,list) and len(fills)>0 and sum((D(str(x['qty'])) for x in fills),D(0))==D('0.002') and all(str(x.get('orderId'))==source['closeOrderId'] for x in fills)
 out['stopHistoryFound']=len(stops)==1
 out['stopHistoryStatuses']=[x.get('algoStatus') for x in stops]
 out['accountFlat']=p==o==a==[]
 out['remaining']={'positions':len(p),'regular':len(o),'conditional':len(a)}
 out['independentPass']=all(out[k] for k in ('entryExact','oneEntryOnly','closeExact','closeFillExact','stopHistoryFound','accountFlat')) and source.get('childExitCode')==73
except Exception as e:
 out['independentPass']=False;out['errorType']=type(e).__name__
finally:s.close()
path=R/'weex_demo_crash_independent_audit_20261109_result.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2));os.replace(tmp,path)
print(json.dumps(out))
