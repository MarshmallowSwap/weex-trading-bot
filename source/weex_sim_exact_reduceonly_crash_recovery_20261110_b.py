"""WEEX API-SIM authenticated crash-after-entry-ACK end-to-end drill.

A real child process sends ONE native-stop entry to strictly allowlisted
api-sim.weex.com, durably records its ACK, then os._exit(79).
A fresh parent process independently reads position, order, native stop;
sends exactly ONE closePositions on API-SIM with stop still active, then
independently checks all records and flat account. NEVER production host.
A per-trial durable journal blocks all reruns of order dispatch.
"""
from __future__ import annotations
import json,os,subprocess,sys,time
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
from weex_pilot_emergency_close_sdk import exact_position_sdk_fields
from weex_pilot_protected_entry_sdk import validate_protected
from weex_pilot_attached_stop_evidence import protected_entry
import live_control,requests

R=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
CLIENT='wxpilot_sim_crash_20261110_b'
FILE=R/'weex_sim_exact_reduceonly_crash_recovery_20261110_b.json'
GETOPS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
 'get_capi_v3_openAlgoOrders','get_capi_v3_allAlgoOrders',
 'get_capi_v3_account_symbolConfig','get_capi_v3_market_ticker_bookTicker',
 'get_capi_v3_order','get_capi_v3_userTrades')
def write(data):
 path=FILE.with_suffix('.tmp')
 path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 os.replace(path,FILE)
def load():
 return json.loads(FILE.read_text(encoding='utf-8'))
class Session:
 def __init__(self,ops,allow_post=None,payload=None):
  self.paths={ops[n]['path'] for n in GETOPS}
  self.allow_post=allow_post
  self.payload=payload
  self.used=False
  self.inner=requests.Session()
 def request(self,method,url,**kw):
  p=urlsplit(url);q=parse_qs(p.query)
  if (p.scheme!='https' or p.netloc!='api-sim.weex.com' or p.fragment
    or kw.get('json') is not None or kw.get('params')):
   raise PermissionError('ONLY_API_SIM_AUTHORIZED')
  if method=='GET':
   if p.path not in self.paths or kw.get('data') not in (None,'',b''):
    raise PermissionError('GET_NOT_ALLOWLISTED')
   if q and not (q=={'symbol':['ETHUSDT']} or
    p.path=='/capi/v3/order' and set(q)=={'orderId'} or
    p.path=='/capi/v3/userTrades' and set(q)=={'symbol','orderId','limit'} and
    q.get('symbol')==['ETHUSDT'] and q.get('limit')==['100']):
    raise PermissionError('READ_QUERY_OUT_OF_SCOPE')
  elif method=='POST':
   if (self.used or p.path!=self.allow_post or p.query or
       json.loads(kw.get('data') or '{}')!=self.payload):
    raise PermissionError('UNSCOPED_OR_DUPLICATE_SIM_ORDER')
   self.used=True
  else:raise PermissionError('ONLY_GET_AND_ONE_SIM_POST')
  kw['allow_redirects']=False
  resp=self.inner.request(method,url,**kw)
  if not 200<=resp.status_code<300:raise RuntimeError('SIM_HTTP_BAD_STATUS')
  return resp
 def close(self):self.inner.close()
def client(ops,session):
 settings,Contract,_=sdk_types()
 credentials=json.loads((R/'weex_sim_v3_credentials.json').read_text(encoding='utf-8'))
 if credentials.get('environment')!='WEEX_SIM_V3':
  raise PermissionError('NOT_SIM_CREDENTIALS')
 return Contract(config_rest_api=settings(base_path=HOST,
  api_key=credentials['api_key'],api_secret=credentials['secret_key'],
  passphrase=credentials['passphrase'],session=session,timeout=8,max_retries=0))
def go():
 if live_control.state(R)['mode']!='STOPPED' or live_control.build_errors(R):
  raise PermissionError('PRODUCTION_NOT_STOPPED_OR_INTEGRITY')
 if FILE.exists():
  print(json.dumps({'status':'ALREADY_RESERVED_NEVER_RESEND','stage':load().get('stage')}))
  return
 initial={'createdAt':datetime.now(timezone.utc).isoformat(),'host':HOST,
  'clientOrderId':CLIENT,'stage':'RESERVED_BEFORE_ENTRY',
  'simEntryPostsMax':1,'simClosePostsMax':1,'productionWrites':0}
 # open exclusive reservation to prevent re-run from concurrent process
 with FILE.open('x',encoding='utf-8') as handle:
  json.dump(initial,handle)
 task=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child'],
  cwd=str(R),capture_output=True,text=True,timeout=35)
 incident=load()
 if (task.returncode!=79 or incident.get('stage')!='ENTRY_ACK_CHILD_CRASHED' or
     not str(incident.get('entryOrderId','')).isdigit()):
  print(json.dumps({'status':'CRASH_NOT_PROVEN_NO_CLOSURE_SUBMITTED',
    'exitCode':task.returncode,'journalStage':incident.get('stage'),
    'childOutputTail':task.stderr[-300:]}))
  return
 recover(incident)
def entry_child():
 if not FILE.is_file() or load().get('stage')!='RESERVED_BEFORE_ENTRY':
  raise PermissionError('ENTRY_JOURNAL_NOT_RESERVED')
 config,Contract,ops=sdk_types()
 sess=Session(ops)
 try:
  with exact_position_sdk_fields():
   api=client(ops,sess)
   def read(n,q=None):return api.rest_api.execute_operation(n,{'query':q or {}}).data
   positions=read('get_capi_v3_account_position_allPosition')
   orders=read('get_capi_v3_openOrders')
   algos=read('get_capi_v3_openAlgoOrders')
   if positions!=[] or orders!=[] or algos!=[]:raise PermissionError('SIM_NOT_FLAT')
   symbol=read('get_capi_v3_account_symbolConfig',{'symbol':'ETHUSDT'})
   if not (isinstance(symbol,list) and len(symbol)==1 and symbol[0].get('marginType')=='ISOLATED'
          and D(str(symbol[0].get('isolatedLongLeverage')))==1):
    raise PermissionError('SIM_NOT_ISOLATED_1X')
   ticker=read('get_capi_v3_market_ticker_bookTicker',{'symbol':'ETHUSDT'})
   ask=D(str(ticker[0]['askPrice']))
   qty=D('0.002');stop=(ask*D('.985')).quantize(D('.01'))
   entry={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
     'quantity':str(qty),'newClientOrderId':CLIENT,
     'slTriggerPrice':str(stop),'SlWorkingType':'MARK_PRICE'}
   validate_protected(entry,str(ask))
   state=load()
   state.update(stage='ENTRY_OUTCOME_UNKNOWN',entry=entry,estimatedNotionalUSDT=str(qty*ask))
   write(state)
   sess.allow_post='/capi/v3/order';sess.payload=entry
   ack=api.rest_api.execute_operation('post_capi_v3_order',{'body':entry})
   if not isinstance(ack.data,dict) or not str(ack.data.get('orderId','')).isdigit():
    raise RuntimeError('SIM_ENTRY_ACK_INVALID')
   state.update(stage='ENTRY_ACK_CHILD_CRASHED',entryOrderId=str(ack.data['orderId']),
                entryAckObserved=True,crashCodeExpected=79,entryChildPid=os.getpid())
   write(state)
   os._exit(79)
 finally:sess.close()
def recover(state):
 config,Contract,ops=sdk_types()
 sess=Session(ops)
 try:
  with exact_position_sdk_fields():
   api=client(ops,sess)
   def read(n,q=None):return api.rest_api.execute_operation(n,{'query':q or {}}).data
   def current():return (read('get_capi_v3_account_position_allPosition'),
                        read('get_capi_v3_openOrders'),
                        read('get_capi_v3_openAlgoOrders'))
   entry=read('get_capi_v3_order',{'orderId':state['entryOrderId']})
   positions,regular,algos=current()
   p=protected_entry({'entry':state['entry']},entry,algos,'LONG','0.002')
   if not (isinstance(positions,list) and len(positions)==1 and regular==[]
           and p.get('verified') is True and len(algos)==1 and
           positions[0].get('marginType')=='ISOLATED' and
           positions[0].get('leverage')=='1' and positions[0].get('size')=='0.002'):
    state.update(stage='STOP_OR_POSITION_NOT_VERIFIED_NO_CLOSE',
      protectionReason=p.get('reason') if isinstance(p,dict) else 'UNKNOWN')
    write(state);return
   pid=str(positions[0]['id']);stopid=str(algos[0]['algoId'])
   state.update(stage='PROTECTED_ENTRY_RECOVERED_BY_NEW_PROCESS',
     recoveryParentPid=os.getpid(),positionId=pid,stopAlgoId=stopid,
     independentStopVerified=True)
   write(state)
   # Exercise the EXACT production-style MARKET reduceOnly /capi/v3/order,
   # not the alternative /closePositions endpoint.
   close={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
      'type':'MARKET','quantity':'0.002',
      'newClientOrderId':'wxclose_sim_crash_20261110_b','reduceOnly':True}
   from weex_http_guard import prepare_sdk_request
   preview=prepare_sdk_request('post_capi_v3_order',close)
   if preview.get('state')!='STOPPED_BEFORE_NETWORK' or preview.get('networkRequests')!=0:
    raise PermissionError('EXACT_REDUCEONLY_SDK_SERIALIZATION_UNVERIFIED')
   # Reserve UNKNOWN before POST and never retry on timeout/crash.
   state.update(stage='CLOSE_OUTCOME_UNKNOWN',close=close,closeAttemptReserved=True)
   write(state)
   sess.allow_post='/capi/v3/order';sess.payload=close
   ack=api.rest_api.execute_operation('post_capi_v3_order',{'body':close})
   rows=ack.data
   if not (isinstance(rows,dict) and rows.get('success') is True and
          str(rows.get('orderId','')).isdigit()):
    state.update(stage='CLOSE_ACK_NOT_VERIFIED');write(state);return
   oid=str(rows['orderId'])
   state.update(stage='CLOSE_ACK_READBACK_REQUIRED',closeOrderId=oid)
   write(state)
   closed=read('get_capi_v3_order',{'orderId':oid})
   fills=read('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':oid,'limit':100})
   nowp,noworders,nowalgos=current()
   hist=read('get_capi_v3_allAlgoOrders',{'symbol':'ETHUSDT'})
   stop_hist=[x for x in hist.get('orders',[]) if str(x.get('algoId'))==stopid]
   ok=(isinstance(closed,dict) and closed.get('status')=='FILLED' and
      closed.get('reduceOnly') is True and closed.get('side')=='SELL' and
      closed.get('positionSide')=='LONG' and D(str(closed.get('executedQty','0')))==D('.002')
      and isinstance(fills,list) and bool(fills) and
      sum((D(str(x['qty'])) for x in fills),D(0))==D('.002')
      and all(str(x.get('orderId'))==oid for x in fills)
      and nowp==[] and noworders==[] and nowalgos==[]
      and len(stop_hist)==1 and stop_hist[0].get('algoStatus') in ('CANCELED','CANCELLED','FILLED'))
   state.update(stage='SIM_CRASH_RECOVERY_FLAT_VERIFIED' if ok else 'SIM_CRASH_RECOVERY_INCOMPLETE',
      exactCloseVerified=bool(ok),accountFlat=nowp==[] and noworders==[] and nowalgos==[],
      terminalStopVerified=len(stop_hist)==1 and stop_hist[0].get('algoStatus') in ('CANCELED','CANCELLED','FILLED'),
      stopStatus=stop_hist[0].get('algoStatus') if len(stop_hist)==1 else None,
      simClosePosts=1,duplicateEntryPosts=0,duplicateClosePosts=0,
      realWorkerCrashCertified=False,productionWrites=0)
   write(state)
   print(json.dumps({k:v for k,v in state.items() if k not in ('entry','close')}))
 finally:sess.close()
if __name__=='__main__':
 if len(sys.argv)==2 and sys.argv[1]=='--child':entry_child()
 elif len(sys.argv)==1:go()
 else:raise SystemExit('UNSUPPORTED_ARGUMENT')
