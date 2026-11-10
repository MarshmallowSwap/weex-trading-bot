"""ONE-SHOT authorized ETHUSDT WEEX V3 CROSS 1x settings change.

Only POST marginType / leverage in that order, never create any order.
Durably reserve every individual POST before network. Do not retry UNKNOWN.
Exact authenticated GET from exchange before and after each setting.
"""
import json,os,requests
from pathlib import Path
from urllib.parse import urlsplit
from weex_http_guard import sdk_types
from weex_live_worker import Reader,ROOT
import live_control

HOST='https://api-contract.weex.com'
SYMBOL='ETHUSDT'
MARGIN={'symbol':SYMBOL,'marginType':'CROSSED','separatedType':'COMBINED'}
LEV={'symbol':SYMBOL,'marginType':'CROSSED','crossLeverage':'1'}
ALLOWED={'/capi/v3/account/marginType':MARGIN,'/capi/v3/account/leverage':LEV}
REPORT=ROOT/'weex_eth_cross_1x_change_receipt_20261109.json'
class OneSettingsPost:
 def __init__(self,path):self.path=path;self.calls=0;self.s=requests.Session()
 def request(self,method,url,**kw):
  u=urlsplit(url)
  if (method!='POST' or url!=HOST+self.path or self.calls or kw.get('params')
      or kw.get('json') is not None or u.fragment):
   raise PermissionError('ONE_EXACT_SETTINGS_POST_ONLY')
  if json.loads(kw.get('data') or '{}')!=ALLOWED[self.path]:
   raise PermissionError('WRONG_WEEX_SETTINGS_BODY')
  self.calls+=1
  kw['allow_redirects']=False
  result=self.s.request(method,url,**kw)
  if 300<=result.status_code<400:raise PermissionError('WEEX_REDIRECT_FORBIDDEN')
  return result
 def close(self):self.s.close()

def save(report):
 t=REPORT.with_suffix('.tmp');t.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 os.replace(t,REPORT)
def check():
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('PRODUCTION_NOT_STOPPED_OR_BUILD_INVALID')
 cfg=json.loads((ROOT/'weex_live_1x_pilot_config.json').read_text())
 if (cfg.get('marginMode')!='CROSS' or cfg.get('leverage')!=1
     or cfg.get('executionEnabled') is not False
     or cfg.get('liveOrderSubmissionAllowed') is not False):
  raise PermissionError('PILOT_CROSS_1X_NOT_DISARMED')
 r=Reader(ROOT)
 positions,regular,algo=r.account()
 if not all(isinstance(x,list) and not x for x in (positions,regular,algo)):
  raise PermissionError('ACCOUNT_NOT_FLAT')
 settings=r.read('get_capi_v3_account_symbolConfig',symbol=SYMBOL)
 if not isinstance(settings,list) or len(settings)!=1 or settings[0].get('symbol')!=SYMBOL:
  raise PermissionError('ETH_CONFIG_UNVERIFIED')
 c=settings[0]
 if c.get('separatedType')!='COMBINED' or c.get('marginType') not in ('CROSSED','CROSS','ISOLATED'):
  raise PermissionError('UNEXPECTED_MARGIN_OR_POSITION_MODE')
 return {k:c.get(k) for k in ('symbol','marginType','separatedType','crossLeverage',
                              'isolatedLongLeverage','isolatedShortLeverage')}

def send(path,operation,expected):
 cfg,Contract,ops=sdk_types()
 if ops[operation]['path']!=path or ops[operation]['method']!='POST':
  raise PermissionError('VENDORED_WEEX_ENDPOINT_CHANGED')
 credentials=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
 session=OneSettingsPost(path)
 try:
  c=Contract(config_rest_api=cfg(base_path=HOST,api_key=credentials['api_key'],
    api_secret=credentials['secret_key'],passphrase=credentials['passphrase'],
    session=session,max_retries=0,timeout=10))
  response=c.rest_api.execute_operation(operation,{'body':ALLOWED[path]})
  if response.status_code!=200:raise RuntimeError('HTTP_SETTINGS_UNCONFIRMED')
  data=response.data
  if path.endswith('marginType'):
   if not isinstance(data,dict) or str(data.get('code'))!='200':
    raise RuntimeError('MARGIN_ACK_UNCONFIRMED')
  elif (not isinstance(data,dict) or data.get('symbol')!=SYMBOL
        or data.get('marginType') not in ('CROSSED','CROSS')
        or str(data.get('crossLeverage'))!='1'):
   raise RuntimeError('CROSS_LEVERAGE_ACK_UNCONFIRMED')
  return {'httpStatus':response.status_code,'responseVerified':True}
 finally:session.close()

def main():
 if REPORT.exists():
  print('ONE_SHOT_ALREADY_RESERVED_NO_RETRY');return
 before=check()
 result={'status':'PREFLIGHT_VERIFIED','requested':{'marginType':'CROSSED','crossLeverage':'1'},
   'before':before,'marginPostReserved':False,'leveragePostReserved':False,
   'ordersSubmitted':0,'botRestarted':False}
 save(result)
 try:
  if before['marginType'] not in ('CROSS','CROSSED'):
   check()
   result.update(status='MARGIN_POST_OUTCOME_UNKNOWN',marginPostReserved=True)
   save(result)
   result['marginAck']=send('/capi/v3/account/marginType',
                            'post_capi_v3_account_marginType',MARGIN)
   result['status']='MARGIN_ACK_NEEDS_READBACK';save(result)
  after=check()
  if after['marginType'] not in ('CROSS','CROSSED') or after['separatedType']!='COMBINED':
   raise RuntimeError('CROSS_MODE_READBACK_FAILED')
  result.update(status='CROSS_MODE_CONFIRMED',afterMargin=after);save(result)
  if str(after['crossLeverage'])!='1':
   check()
   result.update(status='LEVERAGE_POST_OUTCOME_UNKNOWN',leveragePostReserved=True)
   save(result)
   result['leverageAck']=send('/capi/v3/account/leverage',
                           'post_capi_v3_account_leverage',LEV)
   result['status']='LEVERAGE_ACK_NEEDS_READBACK';save(result)
  end=check()
  if end['marginType'] not in ('CROSSED','CROSS') or str(end['crossLeverage'])!='1':
   raise RuntimeError('FINAL_CROSS_1X_READBACK_FAILED')
  result.update(status='CROSS_1X_VERIFIED',final=end);save(result)
 except Exception as exc:
  result.update(status='INCOMPLETE_MANUAL_RECONCILIATION_REQUIRED',errorClass=type(exc).__name__)
  save(result)
 print(json.dumps({'status':result['status'],'before':before,
  'after':result.get('final') or result.get('afterMargin'),
  'marginPostReserved':result['marginPostReserved'],
  'leveragePostReserved':result['leveragePostReserved'],
  'ordersSubmitted':0,'botRestarted':False}))
if __name__=='__main__':main()
