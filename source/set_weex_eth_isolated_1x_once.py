"""ONE-TIME, explicitly authorized ETHUSDT margin+leverage adjustment.
Only POST account/marginType and account/leverage, never orders or transfer.
No retries and no redirects. Stop on ambiguous response; read back before next step.
"""
import json,os
from pathlib import Path
from urllib.parse import urlsplit
import requests
from weex_http_guard import sdk_types,prepare_sdk_request
from weex_live_worker import Reader,ROOT
import live_control

HOST='https://api-contract.weex.com'
SYMBOL='ETHUSDT'
MARGIN={'symbol':SYMBOL,'marginType':'ISOLATED','separatedType':'COMBINED'}
LEV={'symbol':SYMBOL,'marginType':'ISOLATED','isolatedLongLeverage':'1','isolatedShortLeverage':'1'}
ALLOWED={'/capi/v3/account/marginType':MARGIN,'/capi/v3/account/leverage':LEV}
REPORT=ROOT/'weex_eth_isolated_1x_change_receipt.json'
class SingleEndpointSession:
 def __init__(self,path):
  self.path=path;self.calls=0;self.s=requests.Session()
 def request(self,method,url,**kw):
  parsed=urlsplit(url)
  if method!='POST' or url!=HOST+self.path or self.calls!=0 or kw.get('params') or kw.get('json') is not None:
   raise PermissionError('ONLY_ONE_EXACT_SETTINGS_POST')
  data=json.loads(kw.get('data') or '{}')
  if data!=ALLOWED[self.path]:raise PermissionError('WRONG_SETTINGS_PAYLOAD')
  self.calls+=1;kw['allow_redirects']=False
  response=self.s.request(method,url,**kw)
  if 300<=response.status_code<400:raise PermissionError('REDIRECT_FORBIDDEN')
  return response
 def close(self):self.s.close()
def settings(reader):
  arr=reader.read('get_capi_v3_account_symbolConfig',symbol=SYMBOL)
  if not isinstance(arr,list) or len(arr)!=1 or arr[0].get('symbol')!=SYMBOL:raise ValueError('INVALID_SYMBOL_SETTINGS')
  return {k:arr[0].get(k) for k in ('symbol','marginType','separatedType','crossLeverage','isolatedLongLeverage','isolatedShortLeverage')}
def clean():
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('BOT_NOT_STOPPED')
 if live_control.build_errors(ROOT):raise PermissionError('CODE_INTEGRITY_ERROR')
 r=Reader(ROOT);p,o,a=r.account()
 if p or o or a:raise PermissionError('EXISTING_ORDERS_OR_EXPOSURE')
 return settings(r)
def send_settings(path,operation,payload):
 cfg,Contract,_=sdk_types()
 credentials=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
 session=SingleEndpointSession(path)
 try:
  api=Contract(config_rest_api=cfg(base_path=HOST,api_key=credentials['api_key'],
    api_secret=credentials['secret_key'],passphrase=credentials['passphrase'],
    session=session,max_retries=0,timeout=12))
  response=api.rest_api.execute_operation(operation,payload)
  if response.status_code!=200:raise RuntimeError('WEEX_SETTINGS_HTTP_'+str(response.status_code))
  if path.endswith('marginType'):
   if not isinstance(response.data,dict) or str(response.data.get('code'))!='200':
    raise RuntimeError('MARGIN_ACK_UNCONFIRMED')
  elif not isinstance(response.data,dict) or (response.data.get('symbol')!=SYMBOL or
        response.data.get('marginType')!='ISOLATED' or
        str(response.data.get('isolatedLongLeverage'))!='1' or
        str(response.data.get('isolatedShortLeverage'))!='1'):
   raise RuntimeError('LEVERAGE_ACK_UNCONFIRMED')
  return True
 finally:session.close()
def save(report):
 p=REPORT.with_suffix('.tmp')
 p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 os.replace(p,REPORT)
def main():
 if REPORT.exists():raise PermissionError('ONE_TIME_SETTINGS_OPERATION_ALREADY_ATTEMPTED')
 pre=clean()
 report={'status':'NOT_SENT','target':SYMBOL,'requested':{'marginType':'ISOLATED','isolatedLongLeverage':'1','isolatedShortLeverage':'1'},
         'prior':pre,'marginPostAttempted':False,'leveragePostAttempted':False,'ordersSubmitted':0,'botLiveStarted':False}
 if pre['separatedType']!='COMBINED':raise PermissionError('UNEXPECTED_POSITION_MODE')
 try:
  if pre['marginType']!='ISOLATED':
   clean();report.update(status='MARGIN_POST_ATTEMPTED',marginPostAttempted=True);save(report)
   send_settings('/capi/v3/account/marginType','post_capi_v3_account_marginType',MARGIN)
  after_margin=clean()
  if after_margin['marginType']!='ISOLATED' or after_margin['separatedType']!='COMBINED':raise RuntimeError('MARGIN_READBACK_FAILED')
  report.update(status='MARGIN_VERIFIED',afterMargin=after_margin);save(report)
  if after_margin['isolatedLongLeverage']!='1' or after_margin['isolatedShortLeverage']!='1':
   clean();report.update(status='LEVERAGE_POST_ATTEMPTED',leveragePostAttempted=True);save(report)
   send_settings('/capi/v3/account/leverage','post_capi_v3_account_leverage',LEV)
  final=clean()
  if not(final['marginType']=='ISOLATED' and final['separatedType']=='COMBINED' and
       final['isolatedLongLeverage']=='1' and final['isolatedShortLeverage']=='1'):
   raise RuntimeError('FINAL_SETTINGS_NOT_CONFIRMED')
  report.update(status='SUCCESS_VERIFIED',verified=final);save(report)
 except Exception as e:
  report.update(status='INCOMPLETE_REVIEW_REQUIRED',errorClass=type(e).__name__)
  save(report)
  print(json.dumps({'status':report['status'],'errorClass':type(e).__name__,'manualCheckRequired':True,
   'marginPostAttempted':report['marginPostAttempted'],'leveragePostAttempted':report['leveragePostAttempted']}))
  return
 print(json.dumps({'status':report['status'],'settings':final,'botMode':live_control.state(ROOT)['mode'],
    'ordersSubmitted':0}))
if __name__=='__main__':main()
