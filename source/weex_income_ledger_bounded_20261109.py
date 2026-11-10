"""WEEX Futures income ledger read-only semantics (POST /account/income).
No order, account setting, transfer or withdrawal writes. Strict endpoint
and bounded pages; cursor history is preserved without assuming full coverage.
"""
import json,os,requests
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime,timezone
from collections import Counter
from decimal import Decimal
from weex_http_guard import sdk_types
from weex_api_budget import Budget
import live_control
ROOT=Path(__file__).resolve().parent
HOST='https://api-contract.weex.com'
PATH='/capi/v3/account/income'
OUT=ROOT/'weex_income_ledger_bounded_20261109.json'
START=1793132392000 # 2026-10-27 21:39 approximately; corrected below using fills
class IncomeOnly:
 def __init__(self):self.s=requests.Session();self.calls=0
 def request(self,method,url,**kw):
  u=urlsplit(url)
  if method!='POST' or url!=HOST+PATH or u.fragment or kw.get('json') is not None or kw.get('params'):
   raise PermissionError('NON_INCOME_ENDPOINT_BLOCKED')
  data=json.loads(kw.get('data') or '{}')
  if (set(data)-{'asset','symbol','incomeType','startTime','endTime','limit','nextKeyId','nextKeyTime'}
       or data.get('asset')!='USDT' or data.get('limit')!=100
       or not isinstance(data.get('startTime'),int) or not isinstance(data.get('endTime'),int)
       or data['endTime']-data['startTime']>100*86400000):
   raise PermissionError('UNEXPECTED_LEDGER_REQUEST')
  self.calls+=1
  kw['allow_redirects']=False
  # Scoped quota accounting for the officially documented POST/read endpoint.
  # Use the shared ledger and server limits without modifying its protected code.
  import time
  from weex_api_budget import Budget,BudgetDeferred
  b=Budget();b.ensure_limits(timeout=9)
  with b.db() as c:
   c.execute('BEGIN IMMEDIATE');now=b.clock()
   pause=c.execute("SELECT value FROM api_meta_v1 WHERE key='pause'").fetchone()
   if pause and pause[0]>now:raise BudgetDeferred('SHARED_COOLDOWN_ACTIVE')
   limits=c.execute('SELECT kind,seconds,limit_value FROM api_limits_v2').fetchall()
   if not limits:raise BudgetDeferred('NO_EXCHANGE_LIMIT_POLICY')
   for kind,seconds,limit in limits:
    if kind=='REQUEST_WEIGHT' and b._usage(c,kind,seconds,now)+2>limit:
     raise BudgetDeferred('INCOME_LEDGER_REQUEST_WEIGHT_LIMIT')
   c.execute('INSERT INTO api_calls_v1 VALUES(?,?,?,?)',(now,2,0,PATH))
   c.execute("INSERT OR REPLACE INTO api_meta_v1 VALUES('clock',?)",(now,))
  response=self.s.request(method,url,**kw)
  b.observe(response.status_code,response.headers,url)
  return response
 def close(self):self.s.close()
def run():
 if OUT.exists():
  prior=json.loads(OUT.read_text(encoding='utf-8'))
  if prior.get('paginationStatus') not in ('REQUEST_ERROR_BudgetDeferred','REQUEST_ERROR_ApiBusinessError','PAGE_BOUND'):
   print('LEDGER_REPORT_ALREADY_EXISTS');return
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('MAIN_NOT_STOPPED')
 snapshot=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text(encoding='utf-8'))['trades']
 times=[int(x['time']) for x in snapshot]
 start=min(times)-86400000
 import time
 end=min(int(time.time()*1000)-120000,max(times)+86400000)
 cfg,Contract,operations=sdk_types()
 op='post_capi_v3_account_income'
 if operations[op]['path']!=PATH or operations[op]['method']!='POST':
  raise PermissionError('INCOME_OPERATION_CHANGED')
 creds=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
 sess=IncomeOnly()
 client=Contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
  api_secret=creds['secret_key'],passphrase=creds['passphrase'],
  session=sess,max_retries=0,timeout=9))
 rows=[];keys=set();nextkey=None;reason='PAGE_BOUND';pages=0
 for page in range(30):
  body={'asset':'USDT','startTime':start,'endTime':end,'limit':100}
  if nextkey:
   body.update({'nextKeyId':int(nextkey['nextKeyId']),'nextKeyTime':int(nextkey['nextKeyTime'])})
  try:
   response=client.rest_api.execute_operation(op,{'body':body})
   raw=response.data
  except Exception as exc:
   reason='REQUEST_ERROR_'+type(exc).__name__
   message=str(exc)
   print('INCOME_API_ERROR',type(exc).__name__,message[:250])
   break
  if not isinstance(raw,dict) or not isinstance(raw.get('items'),list):
   reason='INVALID_RESPONSE_SHAPE';break
  current=raw['items'];pages+=1
  if len(current)>100:
   reason='OVERSIZED_PAGE';break
  for item in current:
   if not isinstance(item,dict) or not item.get('billId'):
    reason='INVALID_LEDGER_ITEM';break
   key=str(item['billId'])
   if key in keys:
    reason='DUPLICATE_BILL_ID';break
   keys.add(key);rows.append(item)
  if reason in ('INVALID_LEDGER_ITEM','DUPLICATE_BILL_ID'):break
  if raw.get('hasNextPage') is False:
   reason='EXHAUSTED';break
  nextkey=raw.get('nextKey')
  if not isinstance(nextkey,dict) or not nextkey.get('nextKeyId') or not nextkey.get('nextKeyTime'):
   reason='MISSING_NEXT_CURSOR';break
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
   'source':'AUTHENTICATED_WEEX_FUTURES_ACCOUNT_INCOME',
   'endpoint':PATH,'method':'POST_READ_ONLY_SEMANTIC',
   'startMs':start,'endMs':end,'pages':pages,'records':len(rows),
   'paginationStatus':reason,'fullWindowPagination':reason=='EXHAUSTED',
   'types':dict(Counter(str(r.get('incomeType')) for r in rows)),
   'assets':dict(Counter(str(r.get('asset')) for r in rows)),
   'fillFeesFromBillsUSDT':str(sum((Decimal(str(r.get('fillFee') or '0')) for r in rows),Decimal(0))),
   'incomeTotalsByType':{t:str(sum((Decimal(str(r.get('income') or '0')) for r in rows if r.get('incomeType')==t),Decimal(0))) for t in sorted({r.get('incomeType') for r in rows}) if t},
   'rows':rows,'orderWrites':0,'accountSettingsWrites':0,
   'withdrawalOrTransferWrites':0,'liveBotStarted':False,
   'fullAccountingCertified':False}
 temp=OUT.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');os.replace(temp,OUT)
 sess.close()
 print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
if __name__=='__main__':run()
