"""ONE SHOT WEEX SIM-ONLY ETH entry; no production host or credentials output.
Idempotency marker is persisted before the POST, no resend on uncertainty.
"""
import json,os,requests
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
from weex_pilot_protected_entry_sdk import validate_protected
ROOT=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
MARKER=ROOT/'weex_sim_eth_trial_one_shot.json'
OPS=('get_capi_v3_account_balance','get_capi_v3_account_position_allPosition',
 'get_capi_v3_openOrders','get_capi_v3_openAlgoOrders','get_capi_v3_account_symbolConfig',
 'get_capi_v3_market_ticker_bookTicker')
class Session:
 def __init__(self,allowed):self.allowed=allowed;self.used=False;self.s=requests.Session()
 def request(self,method,url,**kw):
  u=urlsplit(url)
  if u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment or kw.get('params') or kw.get('json') is not None:raise PermissionError('WRONG_SIM_TARGET')
  if method=='GET':
   if u.path not in self.allowed or kw.get('data') not in (None,'',b''):raise PermissionError('SIM_READ_NOT_ALLOWED')
   if u.query and (parse_qs(u.query)!={'symbol':['ETHUSDT']} or u.path not in
       ('/capi/v3/account/symbolConfig','/capi/v3/market/ticker/bookTicker')):
    raise PermissionError('SIM_GET_QUERY_UNEXPECTED')
  elif method=='POST':
   if u.path!='/capi/v3/order' or u.query or self.used:raise PermissionError('ENTRY_NOT_EXACT_ONESHOT')
   if json.loads(kw.get('data') or b'{}')!=self.entry:raise PermissionError('ENTRY_PAYLOAD_MISMATCH')
   self.used=True
  else:raise PermissionError('ONLY_SIM_ENTRY_PERMITTED')
  kw['allow_redirects']=False
  r=self.s.request(method,url,**kw)
  if 300<=r.status_code<400:raise PermissionError('SIM_REDIRECT')
  return r
 def close(self):self.s.close()
def save(x):
 t=MARKER.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2),encoding='utf-8');os.replace(t,MARKER)
def run():
 if MARKER.exists():
  print('EXISTING_ONE_SHOT_TRIAL_DO_NOT_RESEND');return
 cfg,contract,ops=sdk_types()
 allowed={ops[n]['path'] for n in OPS}
 creds=json.loads((ROOT/'weex_credentials.json').read_text())
 s=Session(allowed)
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'host':HOST,
   'symbol':'ETHUSDT','stage':'PREFLIGHT','ordersSent':0,'productionWrites':0}
 try:
  c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
    api_secret=creds['secret_key'],passphrase=creds['passphrase'],
    session=s,max_retries=0,timeout=8))
  def read(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
  for n in ('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders','get_capi_v3_openAlgoOrders'):
   rows=read(n)
   if not isinstance(rows,list) or rows:raise PermissionError('SIM_ACCOUNT_NOT_FLAT:'+n)
  setting=read('get_capi_v3_account_symbolConfig',{'symbol':'ETHUSDT'})
  if (not isinstance(setting,list) or len(setting)!=1 or setting[0].get('marginType')!='ISOLATED'
      or any(D(str(setting[0][k]))!=1 for k in ('isolatedLongLeverage','isolatedShortLeverage'))):
   raise PermissionError('SIM_NOT_ISOLATED_1X')
  ticker=read('get_capi_v3_market_ticker_bookTicker',{'symbol':'ETHUSDT'})
  if not isinstance(ticker,list) or len(ticker)!=1:raise PermissionError('SIM_BOOK_MISSING')
  ask=D(str(ticker[0]['askPrice']));qty=D('0.002')
  stop=(ask*D('0.985')).quantize(D('0.01'))
  if qty*ask>5 or stop<=0:raise PermissionError('DEMO_NOTIONAL_BAD')
  client_id='wxpilot_sim_eth_20261108_trial1'
  payload={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG',
    'type':'MARKET','quantity':str(qty),'newClientOrderId':client_id,
    'slTriggerPrice':str(stop),'SlWorkingType':'MARK_PRICE'}
  validate_protected(payload,str(ask))
  report.update(stage='INTENT_DURABLY_RESERVED',clientOrderId=client_id,
    quantity=str(qty),notionalEstimateUSDT=str(qty*ask),stopPrice=str(stop))
  save(report)
  s.entry=payload
  try:
   res=c.rest_api.execute_operation('post_capi_v3_order',{'body':payload})
   report['stage']='HTTP_ACK_NEEDS_EXCHANGE_READBACK'
   report['ordersSent']=1
   report['responseStatusCode']=res.status_code
   if isinstance(res.data,dict):
    report['exchangeOrderId']=str(res.data.get('orderId') or '')
    report['responseSuccess']=res.data.get('success')
  except Exception as exc:
   report['stage']='SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RESEND'
   report['ordersSent']='UNKNOWN'
   report['errorClass']=type(exc).__name__
  save(report)
  print(json.dumps(report))
 except Exception as e:
  report['stage']='PREFLIGHT_FAILED_NO_ORDER'
  report['errorClass']=type(e).__name__
  if not MARKER.exists():save(report)
  print(json.dumps(report))
 finally:s.close()
if __name__=='__main__':run()
