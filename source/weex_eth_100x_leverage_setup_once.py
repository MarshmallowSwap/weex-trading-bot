"""One exact WEEX REAL ETHUSDT CROSS 100x setting, never an order.

Persistent no-retry reservation, fresh empty-account check and official tier
check BEFORE POST, independent authenticated readback AFTER POST.
"""
from __future__ import annotations
import json,os,requests
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
from weex_http_guard import sdk_types,prepare_sdk_request
from weex_api_budget import request as budget_request
from weex_live_worker import Reader
from weex_simple_bot import public
import live_control
ROOT=Path(__file__).resolve().parent
STATE=ROOT/'weex_eth_100x_leverage_setup_once.json'
BODY={'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'100'}
OP='post_capi_v3_account_leverage'
HOST='https://api-contract.weex.com'

def save(value):
 temp=STATE.with_suffix('.tmp')
 temp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
 os.replace(temp,STATE)

def current(reader):
 rows=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
 if not isinstance(rows,list) or len(rows)!=1:
  raise ValueError('EXACT_SYMBOL_SETTING_REQUIRED')
 row=rows[0]
 if row.get('symbol')!='ETHUSDT' or row.get('marginType') not in ('CROSS','CROSSED') or row.get('separatedType')!='COMBINED':
  raise ValueError('ACCOUNT_MODE_INVALID')
 return str(row.get('crossLeverage'))

def preflight(reader=None):
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise ValueError('PRODUCTION_MUST_BE_DISARMED_AND_INTEGRITY_PASS')
 cfg=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
 if cfg['risk']['minimumLeverage']!=100 or cfg['execution']['enabled'] is not False or cfg['execution']['mode']!='PRETRADE':
  raise ValueError('STRATEGY_NOT_PRETRADE_100X')
 reader=reader or Reader(ROOT)
 p,o,a=reader.account()
 if p or o or a:raise ValueError('ACCOUNT_NOT_EMPTY')
 actual=current(reader)
 if actual not in ('50','100'):raise ValueError('UNEXPECTED_OLD_ETH_LEVERAGE')
 x=public('/capi/v3/market/exchangeInfo',symbol='ETHUSDT')
 meta=next(row for row in x['symbols'] if row['symbol']=='ETHUSDT')
 if D(str(meta['maxLeverage']))<100 or D(str(meta['minOrderSize']))!=D('.001'):
  raise ValueError('MINIMUM_CONTRACT_OR_LEVERAGE_CHANGED')
 risk=public('/capi/v3/market/riskLimits',symbol='ETHUSDT')
 tiers=next(row['brackets'] for row in risk if row['symbol']=='ETHUSDT')
 if not any(D(str(t['notionalFloor']))==0 and D(str(t['initialLeverage']))>=100 for t in tiers):
  raise ValueError('100X_RISK_TIER_NOT_PRESENT')
 check=prepare_sdk_request(OP,BODY)
 if check.get('state')!='STOPPED_BEFORE_NETWORK' or check.get('networkRequests')!=0:
  raise ValueError('SDK_SERIALIZATION_NOT_VERIFIED')
 return actual

class OnlyLeverage:
 def __init__(self):self.session=requests.Session();self.attempts=0
 def request(self,method,url,**kw):
  parsed=urlsplit(url)
  if (self.attempts or method!='POST' or parsed.scheme!='https'
     or parsed.netloc!='api-contract.weex.com' or parsed.path!='/capi/v3/account/leverage'
     or parsed.query or parsed.fragment or kw.get('json') is not None or kw.get('params')
     or json.loads(kw.get('data') or '{}')!=BODY):
   raise PermissionError('UNSCOPED_SETTING_WRITE')
  self.attempts+=1;kw['allow_redirects']=False
  r=budget_request(self.session,method,url,**kw)
  if r.status_code!=200:raise RuntimeError('WEEX_SETTING_OUTCOME_UNKNOWN')
  return r
 def close(self):self.session.close()

def run():
 out={'status':'BLOCKED','symbol':'ETHUSDT','targetLeverage':100,
   'ordersSent':0,'automaticBotActivated':False}
 if STATE.exists():
  # Any previous attempt, including uncertain outcomes, forbids repeat POST.
  try:
   value=json.loads(STATE.read_text(encoding='utf-8'))
   actual=current(Reader(ROOT))
   if actual=='100':
    value['status']='VERIFIED';value['source']='EXCHANGE_READBACK_NO_RESEND';save(value)
    out.update(status='VERIFIED_FROM_READBACK_NO_RESEND')
   else:out.update(status='UNKNOWN_NO_RETRY',actualLeverage=actual)
  except Exception as exc:out.update(status='UNKNOWN_NO_RETRY',reason=type(exc).__name__)
  return out
 try:actual=preflight()
 except Exception as exc:
  out.update(reason=type(exc).__name__,detail=str(exc) if isinstance(exc,ValueError) else None)
  return out
 if actual=='100':out.update(status='ALREADY_100X_NO_WRITE');return out
 record={'createdAt':datetime.now(timezone.utc).isoformat(),
  'status':'REQUEST_RESERVED','scope':'ETHUSDT_CROSSED_100X_SETTING_ONLY',
  'body':BODY,'maximumSettingPOSTs':1,'ordersAllowed':0}
 save(record) # persist before any network
 transport=OnlyLeverage()
 try:
  config,contract,ops=sdk_types()
  creds=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
  client=contract(config_rest_api=config(base_path=HOST,
   api_key=creds['api_key'],api_secret=creds['secret_key'],
   passphrase=creds['passphrase'],session=transport,timeout=10,max_retries=0))
  response=client.rest_api.execute_operation(OP,{'body':BODY})
  record['status']='POST_ACK_READBACK_PENDING';record['httpStatus']=response.status_code
  save(record)
 except Exception as exc:
  record['status']='OUTCOME_UNKNOWN_NO_RETRY';record['errorType']=type(exc).__name__
  save(record)
 finally:transport.close()
 try:
  if current(Reader(ROOT))=='100':
   record['status']='VERIFIED';record['source']='EXCHANGE_SYMBOL_CONFIGURATION_READBACK'
   save(record)
   out.update(status='VERIFIED_100X',settingWritesAttempted=transport.attempts)
  else:out.update(status='UNKNOWN_NO_RETRY',reason='NOT_CONFIRMED_100X')
 except Exception as exc:out.update(status='UNKNOWN_NO_RETRY',reason=type(exc).__name__)
 return out

if __name__=='__main__':
 print(json.dumps(run(),ensure_ascii=False))
