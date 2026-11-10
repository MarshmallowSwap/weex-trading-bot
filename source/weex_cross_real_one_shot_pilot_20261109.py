"""Single expressly authorized ETHUSDT CROSS 1x real-money pilot.
MAX ONE protected BUY and ONE exact-position close; NO BOT RESTART.
Durable no-retry attempts; real account MUST be flat and CROSS 1x.
This standalone pilot has narrower scope than the general production bot.
"""
import json,os,requests,time
from pathlib import Path
from decimal import Decimal as D
from urllib.parse import urlsplit,parse_qs
from datetime import datetime,timezone
from weex_http_guard import sdk_types
from weex_pilot_emergency_close_sdk import exact_position_sdk_fields
from weex_pilot_protected_entry_sdk import validate_protected
from weex_pilot_attached_stop_evidence import protected_entry
import live_control
ROOT=Path(__file__).resolve().parent
HOST='https://api-contract.weex.com'
STATE=ROOT/'weex_cross_one_shot_real_pilot_20261109.json'
CID='wxpilot_cross_eth_20261109_one1'
GETS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
 'get_capi_v3_openAlgoOrders','get_capi_v3_allAlgoOrders',
 'get_capi_v3_account_balance','get_capi_v3_account_symbolConfig',
 'get_capi_v3_market_ticker_bookTicker','get_capi_v3_order',
 'get_capi_v3_userTrades')
class LimitedTransport:
 def __init__(self,ops):
  self.s=requests.Session();self.getpaths={ops[n]['path'] for n in GETS}
  self.entry=None;self.exit=None;self.used=set()
 def request(self,method,url,**kw):
  u=urlsplit(url);q=parse_qs(u.query)
  if (u.scheme!='https' or u.netloc!='api-contract.weex.com' or u.fragment
      or kw.get('params') or kw.get('json') is not None):
   raise PermissionError('WRONG_DESTINATION')
  if method=='GET':
   if u.path not in self.getpaths or kw.get('data') not in (None,'',b''):
    raise PermissionError('UNEXPECTED_GET')
   if q and not (q=={'symbol':['ETHUSDT']} or
    u.path=='/capi/v3/order' and set(q)=={'orderId'} and len(q['orderId'])==1 or
    u.path=='/capi/v3/userTrades' and set(q)=={'symbol','orderId','limit'} and
    q['symbol']==['ETHUSDT'] and q['limit']==['100'] and len(q['orderId'])==1):
    raise PermissionError('UNEXPECTED_QUERY')
  elif method=='POST':
   if u.query or u.path not in ('/capi/v3/order','/capi/v3/closePositions'):
    raise PermissionError('UNAUTHORIZED_WRITE_PATH')
   typ='ENTRY' if u.path=='/capi/v3/order' else 'EXIT'
   payload=self.entry if typ=='ENTRY' else self.exit
   if typ in self.used or payload is None or json.loads(kw.get('data') or '{}')!=payload:
    raise PermissionError('UNAUTHORIZED_OR_DUPLICATE_WRITE')
   self.used.add(typ)
  else:raise PermissionError('NO_OTHER_WRITE_ALLOWED')
  kw['allow_redirects']=False
  resp=self.s.request(method,url,**kw)
  if not 200<=resp.status_code<300:raise RuntimeError('WEEX_HTTP_NON_SUCCESS')
  return resp
 def close(self):self.s.close()
def save(state):
 t=STATE.with_suffix('.tmp')
 t.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 os.replace(t,STATE)
def run():
 if STATE.exists():print('ONE_SHOT_ALREADY_RESERVED_DO_NOT_RESEND');return
 config=json.loads((ROOT/'weex_live_1x_pilot_config.json').read_text())
 demo=json.loads((ROOT/'weex_pilot_demo_exit_certification_20261109.json').read_text())
 if (config.get('marginMode')!='CROSS' or config.get('leverage')!=1
     or config.get('maxNewOrders')!=1
     or D(str(config.get('maxAdditionalNotionalUSDT','0')))>5
     or config.get('executionEnabled') is not False
     or config.get('liveOrderSubmissionAllowed') is not False):
  raise PermissionError('SINGLE_PILOT_SCOPE_NOT_DISARMED')
 if (demo.get('demoProtectedEmergencyCloseCertified') is not True
     or demo.get('demoReduceOnlyExitCertified') is not True):
  raise PermissionError('EXIT_DEMO_NOT_CERTIFIED')
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('BOT_NOT_STOPPED_OR_MANIFEST_BAD')
 sdk,Contract,ops=sdk_types()
 creds=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
 sess=LimitedTransport(ops)
 state={'createdAt':datetime.now(timezone.utc).isoformat(),'host':HOST,
   'clientOrderId':CID,'stage':'PREFLIGHT','entryAttemptReserved':False,
   'closeAttemptReserved':False,'entryPostCount':0,'closePostCount':0,
   'stopCancellationRequests':0,'mainBotRestarted':False}
 save(state)
 try:
  with exact_position_sdk_fields():
   api=Contract(config_rest_api=sdk(base_path=HOST,api_key=creds['api_key'],
     api_secret=creds['secret_key'],passphrase=creds['passphrase'],
     session=sess,timeout=8,max_retries=0))
   def read(n,q=None):return api.rest_api.execute_operation(n,{'query':q or {}}).data
   def account():
    return (read('get_capi_v3_account_position_allPosition'),
      read('get_capi_v3_openOrders'),read('get_capi_v3_openAlgoOrders'))
   p,o,a=account()
   if p!=[] or o!=[] or a!=[]:raise PermissionError('PRODUCTION_ACCOUNT_NOT_FLAT')
   cfg=read('get_capi_v3_account_symbolConfig',{'symbol':'ETHUSDT'})
   if (not isinstance(cfg,list) or len(cfg)!=1 or
       cfg[0].get('marginType') not in ('CROSS','CROSSED') or
       D(str(cfg[0].get('crossLeverage','0')))!=1 or
       cfg[0].get('separatedType')!='COMBINED'):
    raise PermissionError('EXCHANGE_NOT_CROSS_1X')
   balance=read('get_capi_v3_account_balance')
   if (not isinstance(balance,list) or not any(x.get('asset')=='USDT'
        and D(str(x.get('availableBalance','0')))>=D('5') for x in balance)):
    raise PermissionError('INSUFFICIENT_BALANCE')
   ticker=read('get_capi_v3_market_ticker_bookTicker',{'symbol':'ETHUSDT'})
   if not isinstance(ticker,list) or len(ticker)!=1:
    raise PermissionError('LIVE_TICKER_INVALID')
   ask=D(str(ticker[0]['askPrice']));qty=D('.002')
   stop=(ask*D('.985')).quantize(D('.01'))
   if not ask.is_finite() or ask<=0 or qty*ask>D('4.9'):
    raise PermissionError('NOTIONAL_CAP_OR_PRICE_INVALID')
   payload={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
    'quantity':str(qty),'newClientOrderId':CID,
    'slTriggerPrice':str(stop),'SlWorkingType':'MARK_PRICE'}
   validate_protected(payload,str(ask))
   if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('MAIN_NOT_STOPPED')
   state.update(stage='ENTRY_OUTCOME_UNKNOWN',entryAttemptReserved=True,
       indicativeNotionalUSDT=str(qty*ask),stopPrice=str(stop))
   save(state)
   sess.entry=payload
   try:
    resp=api.rest_api.execute_operation('post_capi_v3_order',{'body':payload})
    state['entryPostCount']=1
    data=resp.data
    if not isinstance(data,dict) or data.get('success') is not True or not data.get('orderId'):
     raise ValueError('ENTRY_ACK_UNVERIFIED')
    oid=str(data['orderId'])
    state.update(stage='ENTRY_ACK_NEEDS_READBACK',entryOrderId=oid)
    save(state)
   except Exception as exc:
    state.update(stage='ENTRY_OUTCOME_UNKNOWN',entryErrorClass=type(exc).__name__)
    save(state);print(json.dumps(state));return
   order=None
   for _ in range(3):
    order=read('get_capi_v3_order',{'orderId':oid})
    p,o,a=account()
    if (isinstance(order,dict) and order.get('status')=='FILLED'
        and len(p)==1 and len(a)==1):break
    time.sleep(.4)
   fills=read('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':oid,'limit':100})
   proof=protected_entry({'entry':payload},order,a,'LONG',str(qty))
   from decimal import Decimal
   fqty=sum((D(str(f['qty'])) for f in fills),D(0)) if isinstance(fills,list) else D(0)
   if (proof.get('verified') is not True or not isinstance(p,list) or len(p)!=1
       or not isinstance(o,list) or o or fqty!=qty or
       p[0].get('marginType') not in ('CROSS','CROSSED') or
       p[0].get('leverage')!='1' or p[0].get('side')!='LONG'
       or D(str(p[0].get('size','0')))!=qty or not p[0].get('id')):
    state.update(stage='ENTRY_OR_EXCHANGE_STOP_READBACK_INCOMPLETE',
      stopProof=proof.get('reason'),openPositions=len(p) if isinstance(p,list) else None)
    save(state);print(json.dumps(state));return
   positionId=str(p[0]['id'])
   state.update(stage='PROTECTED_CROSS_POSITION_VERIFIED',positionId=positionId,
     stopAlgoId=str(a[0]['algoId']),stopVerified=True)
   save(state)
   # Exactly one close by independently observed position ID while stop active.
   close={'symbol':'ETHUSDT','positionId':int(positionId)}
   sess.exit=close
   state.update(stage='CLOSE_OUTCOME_UNKNOWN',closeAttemptReserved=True)
   save(state)
   try:
    res=api.rest_api.execute_operation('post_capi_v3_closePositions',{'body':close})
    state['closePostCount']=1
    rows=res.data
    if not isinstance(rows,list) or len(rows)!=1 or str(rows[0].get('positionId'))!=positionId or rows[0].get('success') is not True:
     raise ValueError('CLOSE_ACK_UNVERIFIED')
    close_oid=str(rows[0].get('successOrderId') or '')
    if not close_oid:raise ValueError('CLOSE_ORDER_ID_MISSING')
    state.update(stage='CLOSE_ACK_NEEDS_READBACK',closeOrderId=close_oid)
    save(state)
   except Exception as exc:
    state.update(stage='CLOSE_OUTCOME_UNKNOWN',closeErrorClass=type(exc).__name__)
    save(state);print(json.dumps(state));return
   for _ in range(3):
    p,o,a=account()
    if p==[] and o==[] and a==[]:break
    time.sleep(.4)
   close_order=read('get_capi_v3_order',{'orderId':close_oid})
   close_fills=read('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':close_oid,'limit':100})
   history=read('get_capi_v3_allAlgoOrders',{'symbol':'ETHUSDT'})
   close_ok=(isinstance(close_order,dict) and close_order.get('status')=='FILLED'
     and close_order.get('reduceOnly') is True
     and str(close_order.get('orderId'))==close_oid
     and D(str(close_order.get('executedQty','0')))==qty
     and isinstance(close_fills,list) and bool(close_fills)
     and sum((D(str(x['qty'])) for x in close_fills),D(0))==qty
     and all(str(f.get('orderId'))==close_oid for f in close_fills))
   stop_terminal=(isinstance(history,dict) and
     any(str(x.get('algoId'))==state['stopAlgoId'] and
     x.get('algoStatus') in ('CANCELED','CANCELLED')
     for x in history.get('orders',[]) if isinstance(x,dict)))
   state.update(stage='CROSS_PILOT_CLOSED_AND_VERIFIED' if
      close_ok and stop_terminal and p==[] and o==[] and a==[]
      else 'CLOSE_RECONCILIATION_INCOMPLETE',
      closeReduceOnlyVerified=close_ok,stopTerminalVerified=stop_terminal,
      accountFlatVerified=p==[] and o==[] and a==[],
      positionsRemaining=len(p) if isinstance(p,list) else None,
      openAlgosRemaining=len(a) if isinstance(a,list) else None)
   save(state)
 except Exception as exc:
  state.update(stage='INTERRUPTED_REQUIRES_MANUAL_EXCHANGE_RECONCILIATION',
    errorClass=type(exc).__name__)
  save(state)
 finally:
  sess.close()
 print(json.dumps(state))
if __name__=='__main__':run()
