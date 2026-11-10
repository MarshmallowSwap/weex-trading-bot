"""Only WEEX documented account-income history for JCTUSDT funding.
This SDK endpoint uses HTTP POST but is a read-only *account history* query.
The transport refuses EVERY other POST path and payload and all order methods.
No response containing credentials, balance or account identifiers is printed.
"""
import json
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
from weex_http_guard import sdk_types
from weex_live_worker import ROOT
import live_control

START=1793925553208
END=1793932747500
BODY={'asset':'USDT','symbol':'JCTUSDT','incomeType':'position_funding',
      'startTime':START-1000,'endTime':END+1000,'limit':100}
URL='https://api-contract.weex.com/capi/v3/account/income'
class OnlyFundingHistory:
 def __init__(self):
  import requests
  self.client=requests.Session()
  self.calls=0
 def request(self,method,url,**kw):
  if (method!='POST' or url!=URL or self.calls!=0 or kw.get('params')
      or kw.get('json') is not None or kw.get('allow_redirects') is True):
   raise PermissionError('ACCOUNT_HISTORY_ONLY')
  data=json.loads(kw.get('data') or '{}')
  if data!=BODY:raise PermissionError('EXACT_FUNDING_HISTORY_PAYLOAD_REQUIRED')
  self.calls+=1
  kw['allow_redirects']=False
  r=self.client.request(method,url,**kw)
  if 300<=r.status_code<400:raise PermissionError('REDIRECT_DISALLOWED')
  return r
 def close(self):self.client.close()
def main():
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('LIVE_MUST_BE_STOPPED')
 from weex_common.configuration import ConfigurationRestAPI
 from weex_contract_sdk import Contract
 cred=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
 session=OnlyFundingHistory()
 try:
  c=Contract(config_rest_api=ConfigurationRestAPI(base_path='https://api-contract.weex.com',
    api_key=cred['api_key'],api_secret=cred['secret_key'],passphrase=cred['passphrase'],
    session=session,max_retries=0,timeout=12))
  response=c.rest_api.execute_operation('post_capi_v3_account_income',BODY)
  if response.status_code!=200:raise ValueError('HISTORY_HTTP_STATUS_'+str(response.status_code))
  data=response.data
  if not isinstance(data,dict) or not isinstance(data.get('items'),list):
   raise ValueError('INVALID_INCOME_HISTORY')
  rows=data['items']
  parsed=[]
  for item in rows:
   if (item.get('symbol')!='JCTUSDT' or item.get('asset')!='USDT'
      or item.get('incomeType')!='position_funding'):
    raise ValueError('UNEXPECTED_FUNDING_ROW')
   stamp=int(item['time'])
   if START<=stamp<=END:
    parsed.append({'atUTC':datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
      'incomeUSDT':str(D(str(item['income'])))})
  print(json.dumps({'query':'JCTUSDT_ACCOUNT_FUNDING_ONLY',
       'window':{'start':START,'end':END},
       'rowsInResponse':len(rows),'hasNextPage':data.get('hasNextPage'),
       'fundingRowsDuringPosition':parsed,
       'fundingIncomeSignedUSDT':str(sum((D(x['incomeUSDT']) for x in parsed),D(0))),
       'complete':data.get('hasNextPage') is False,
       'accountOrdersSubmitted':0,'requestPath':'/capi/v3/account/income',
       'requestCount':session.calls,'liveMode':live_control.state(ROOT)['mode']}))
 finally:session.close()
if __name__=='__main__':main()
