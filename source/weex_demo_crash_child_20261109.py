"""ONE-SHOT API-SIM: close exact ETH position while its stop remains active.
No production network, no stop cancel, no retry. Save durable write intentions.
"""
import json,os,requests
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
from weex_pilot_emergency_close_sdk import exact_position_sdk_fields
from weex_pilot_protected_entry_sdk import validate_protected
from weex_pilot_attached_stop_evidence import protected_entry
import live_control
R=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
FILE=R/'weex_demo_crash_child_state_20261109.json'
CLIENT='wxpilot_crashsim_20261109a01'
GETOPS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
 'get_capi_v3_openAlgoOrders','get_capi_v3_account_symbolConfig',
 'get_capi_v3_market_ticker_bookTicker','get_capi_v3_order',
 'get_capi_v3_userTrades')
def save(r):
 tmp=FILE.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2));os.replace(tmp,FILE)
class SimSession:
 def __init__(self,ops):
  self.paths={ops[x]['path'] for x in GETOPS}
  self.s=requests.Session();self.entry=None;self.close_body=None;self.used=set()
 def request(self,method,url,**kw):
  u=urlsplit(url);q=parse_qs(u.query)
  if u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment or kw.get('json') is not None or kw.get('params'):
   raise PermissionError('PRODUCTION_OR_REDIRECT_NOT_ALLOWED')
  if method=='GET':
   if u.path not in self.paths or kw.get('data') not in (None,'',b''):
    raise PermissionError('SIM_READ_DENIED')
   if q and not (q=={'symbol':['ETHUSDT']} or
     u.path=='/capi/v3/order' and set(q)=={'orderId'} or
     u.path=='/capi/v3/userTrades' and q.get('symbol')==['ETHUSDT'] and q.get('limit')==['100'] and len(q.get('orderId',[]))==1):
    raise PermissionError('SIM_READ_QUERY_DENIED')
  elif method=='POST':
   expected='/capi/v3/order' if u.path=='/capi/v3/order' else '/capi/v3/closePositions'
   key='entry' if expected=='/capi/v3/order' else 'close'
   payload=self.entry if key=='entry' else self.close_body
   if u.path!=expected or key in self.used or payload is None or u.query or json.loads(kw.get('data') or '{}')!=payload:
    raise PermissionError('SIM_WRITE_NOT_EXACT')
   self.used.add(key)
  else:raise PermissionError('SIM_ONLY_GET_AND_EXACT_TWO_POSTS')
  kw['allow_redirects']=False
  response=self.s.request(method,url,**kw)
  if not 200<=response.status_code<300:raise RuntimeError('WEEX_SIM_HTTP_NON_SUCCESS')
  return response
 def shutdown(self):self.s.close()

def run():
 if FILE.exists():print('SIM_ONE_SHOT_ALREADY_RESERVED_NO_RETRY');return
 if live_control.state(R)['mode']!='STOPPED' or live_control.build_errors(R):
  raise PermissionError('PRODUCTION_NOT_STOPPED')
 cfg,contract,ops=sdk_types()
 creds=json.loads((R/'weex_sim_v3_credentials.json').read_text());assert creds.get('environment')=='WEEX_SIM_V3'
 s=SimSession(ops)
 result={'checkedAt':datetime.now(timezone.utc).isoformat(),'host':HOST,'clientId':CLIENT,
  'stage':'PREFLIGHT','entryAttemptReserved':False,'closeAttemptReserved':False,
  'productionWrites':0,'simEntryPosts':0,'simClosePosts':0,'stopCancellationPosts':0}
 save(result)
 try:
  with exact_position_sdk_fields():
   c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
    api_secret=creds['secret_key'],passphrase=creds['passphrase'],
    session=s,max_retries=0,timeout=8))
   def read(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
   def state():return (read('get_capi_v3_account_position_allPosition'),
      read('get_capi_v3_openOrders'),read('get_capi_v3_openAlgoOrders'))
   p,o,a=state()
   if p!=[] or o!=[] or a!=[]:raise PermissionError('SIM_NOT_FLAT')
   setting=read('get_capi_v3_account_symbolConfig',{'symbol':'ETHUSDT'})
   if not (isinstance(setting,list) and len(setting)==1 and
      setting[0].get('marginType')=='ISOLATED' and
      D(str(setting[0]['isolatedLongLeverage']))==D(1)):raise PermissionError('SIM_NOT_ISOLATED_1X')
   ticker=read('get_capi_v3_market_ticker_bookTicker',{'symbol':'ETHUSDT'})
   ask=D(str(ticker[0]['askPrice']));qty=D('0.002')
   stop=(ask*D('0.985')).quantize(D('0.01'))
   payload={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
       'quantity':str(qty),'newClientOrderId':CLIENT,
       'slTriggerPrice':str(stop),'SlWorkingType':'MARK_PRICE'}
   validate_protected(payload,str(ask))
   result.update(stage='ENTRY_OUTCOME_UNKNOWN',entryAttemptReserved=True,
      estimatedNotionalUSDT=str(qty*ask),stopPrice=str(stop))
   save(result);s.entry=payload
   try:
    ack=c.rest_api.execute_operation('post_capi_v3_order',{'body':payload})
    os._exit(73)
    result['simEntryPosts']=1
    result['entryOrderId']=str(ack.data.get('orderId') or '')
    result['stage']='ENTRY_ACK_NEEDS_READBACK';save(result)
   except Exception as ex:
    result.update(stage='ENTRY_OUTCOME_UNKNOWN',errorClass=type(ex).__name__)
    save(result);return
   oid=result['entryOrderId']
   if not oid:raise PermissionError('ENTRY_ID_MISSING')
   order=read('get_capi_v3_order',{'orderId':oid})
   p,o,a=state()
   pr={'entry':payload}
   proof=protected_entry(pr,order,a,'LONG',str(qty))
   if not (isinstance(p,list) and len(p)==1 and not o and
      proof['verified'] is True and p[0].get('marginType')=='ISOLATED'
      and p[0].get('leverage')=='1' and p[0].get('size')==str(qty)):
    result.update(stage='ENTRY_STOP_OR_POSITION_NOT_VERIFIED',
       protectionReason=proof.get('reason'),positionCount=len(p) if isinstance(p,list) else None)
    save(result);return
   position_id=str(p[0]['id'])
   result.update(stage='ACTIVE_STOP_INDEPENDENTLY_VERIFIED',
      stopAlgoId=str(a[0]['algoId']),positionId=position_id,
      stopVerifiedBeforeClose=True,stopCanceledBeforeClose=False)
   save(result)
   # One exact positionId close while STOP_MARKET is still active.
   close={'symbol':'ETHUSDT','positionId':int(position_id)}
   s.close_body=close
   result.update(stage='CLOSE_OUTCOME_UNKNOWN',closeAttemptReserved=True)
   save(result)
   try:
    response=c.rest_api.execute_operation('post_capi_v3_closePositions',{'body':close})
    result['simClosePosts']=1
    records=response.data
    if not (isinstance(records,list) and len(records)==1 and
        str(records[0].get('positionId'))==position_id and
        records[0].get('success') is True):
     result.update(stage='CLOSE_REJECTED_OR_UNVERIFIED',closeResponse=records)
     save(result);return
    result.update(stage='CLOSE_ACK_NEEDS_READBACK',
        closeOrderId=str(records[0].get('successOrderId') or ''))
    save(result)
   except Exception as ex:
    result.update(stage='CLOSE_OUTCOME_UNKNOWN',closeErrorClass=type(ex).__name__)
    save(result);return
   p,o,a=state()
   result.update(postClosePositions=len(p) if isinstance(p,list) else None,
     postCloseRegularOrders=len(o) if isinstance(o,list) else None,
     postCloseConditionalAlgos=len(a) if isinstance(a,list) else None,
     remainingStopAlgoIds=[str(x.get('algoId')) for x in a] if isinstance(a,list) else [],
     stopCanceledBeforeClose=False,
     positionFlatVerified=p==[] and o==[])
   cid=result['closeOrderId']
   if cid:
    closed=read('get_capi_v3_order',{'orderId':cid})
    fills=read('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':cid,'limit':100})
    result['reduceOnlyCloseVerified']=(isinstance(closed,dict) and
      closed.get('status')=='FILLED' and closed.get('reduceOnly') is True and
      closed.get('symbol')=='ETHUSDT' and closed.get('side')=='SELL' and
      D(str(closed.get('executedQty','0')))==qty and
      isinstance(fills,list) and bool(fills) and
      sum((D(str(f['qty'])) for f in fills),D(0))==qty)
   result['stage']='SIM_ACTIVE_STOP_CLOSE_VERIFIED' if result.get('positionFlatVerified') and result.get('reduceOnlyCloseVerified') else 'SIM_CLOSE_NEEDS_FURTHER_READBACK'
   save(result)
 except Exception as ex:
  result.update(stage='SIM_INTERRUPTED_REQUIRES_READBACK',errorClass=type(ex).__name__)
  save(result)
 finally:
  s.shutdown()
  print(json.dumps(result))
if __name__=='__main__':run()
