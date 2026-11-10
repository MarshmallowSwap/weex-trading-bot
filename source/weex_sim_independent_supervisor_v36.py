"""Independent WEEX API-SIM incident supervisor V36.

This OS process observes exact real SIM position/order/stop, starts the genuine
production worker recovery CLI through v8 with SIM-only authenticated proof
adapter, then performs ONE independently reserved SIM closePositions POST.
No production host, credentials, exit permit, or CROSS trading.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,time,requests
from pathlib import Path
from decimal import Decimal as D
from urllib.parse import urlsplit,parse_qs
from weex_http_guard import sdk_types
from weex_pilot_attached_stop_evidence import protected_entry
from weex_supervised_process_monitor_v6 import tick
from weex_supervised_worker_recovery_process_v8 import recover
from weex_supervised_crash_executor_v2 import CLIENT_ID as PROD_CLIENT
from weex_independent_supervisor_replay_v35 import CHILD_CODE
import live_control

ROOT=Path(__file__).resolve().parent
HOST='https://api-sim.weex.com'
GETS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
      'get_capi_v3_openAlgoOrders','get_capi_v3_order_history')
class SimOnlyCloseSession:
 def __init__(self,ops):
  self.paths={ops[k]['path'] for k in GETS}
  self.s=requests.Session();self.close_payload=None;self.calls=0
 def request(self,method,url,**kw):
  u=urlsplit(url);q=parse_qs(u.query)
  if (u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment
      or kw.get('json') is not None or kw.get('params')):raise PermissionError('PRODUCTION_HOST_DENIED')
  if method=='GET':
   if (u.path not in self.paths or kw.get('data') not in (None,'',b'')
       or (q and q!={'symbol':['ETHUSDT']})):raise PermissionError('SIM_GET_NOT_ALLOWED')
  elif method=='POST':
   if (self.calls!=0 or u.path!='/capi/v3/closePositions'
       or u.query or self.close_payload is None
       or json.loads(kw.get('data') or '{}')!=self.close_payload):
    raise PermissionError('REPEATED_OR_WRONG_CLOSE')
   self.calls+=1
  else:raise PermissionError('NO_OTHER_HTTP_METHODS')
  kw['allow_redirects']=False
  r=self.s.request(method,url,**kw)
  if not 200<=r.status_code<300:raise RuntimeError('SIM_HTTP_FAILED')
  return r
 def shutdown(self):self.s.close()

def execute(root,manifest):
 root=Path(root).resolve();m=json.loads(Path(manifest).read_text(encoding='utf-8'))
 if root==ROOT.resolve() or ROOT.resolve() in root.parents:raise PermissionError('SIM_STATE_MUST_BE_SEPARATE')
 if (root/'weex_credentials.json').exists():raise PermissionError('PRODUCTION_CREDS_PROHIBITED')
 if (root/'weex_sim_supervisor_once.json').exists():raise PermissionError('SIM_SUPERVISOR_ALREADY_ATTEMPTED')
 if m.get('host')!=HOST or m.get('clientId')!='wxpilot_crashsim_v36a01' or m.get('childExitCode')!=73:
  raise PermissionError('INVALID_SIM_CRASH_MANIFEST')
 if m.get('stage')!='ENTRY_OUTCOME_UNKNOWN' or not str(m.get('entryOrderId','')).isdigit():
  raise PermissionError('NOT_DURABLE_UNKNOWN_ENTRY')
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('PRODUCTION_NOT_STOPPED')
 creds=json.loads((ROOT/'weex_sim_v3_credentials.json').read_text(encoding='utf-8'))
 if creds.get('environment')!='WEEX_SIM_V3':raise PermissionError('NOT_SIM_CREDENTIALS')
 cfg,Contract,ops=sdk_types()
 session=SimOnlyCloseSession(ops)
 api=Contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
   api_secret=creds['secret_key'],passphrase=creds['passphrase'],
   session=session,timeout=8,max_retries=0))
 def get(name,q=None):return api.rest_api.execute_operation(name,{'query':q or {}}).data
 events=[]
 def exact_observation():
  positions=get('get_capi_v3_account_position_allPosition')
  regular=get('get_capi_v3_openOrders')
  stops=get('get_capi_v3_openAlgoOrders')
  history=get('get_capi_v3_order_history',{'symbol':'ETHUSDT'})
  records=history.get('orders',[]) if isinstance(history,dict) else history if isinstance(history,list) else []
  matches=[r for r in records if isinstance(r,dict) and r.get('clientOrderId')==m['clientId']]
  if (len(matches)!=1 or len(positions)!=1 or len(stops)!=1 or regular!=[]
       or str(matches[0].get('orderId'))!=m['entryOrderId']
       or matches[0].get('status')!='FILLED'):
   raise ValueError('SIM_EXACT_ACCOUNT_NOT_VERIFIED')
  p=positions[0];stop=stops[0]
  if (p.get('symbol')!='ETHUSDT' or p.get('side')!='LONG'
      or D(str(p.get('size')))!=D('0.002')
      or p.get('marginType')!='ISOLATED' or str(p.get('leverage'))!='1'
      or not str(p.get('id','')).isdigit()
      or not str(stop.get('algoId','')).isdigit()):
   raise ValueError('SIM_POSITION_SCOPE_MISMATCH')
  payload={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
   'quantity':'0.002','newClientOrderId':m['clientId'],
   'slTriggerPrice':str(m['stopPrice']),'SlWorkingType':'MARK_PRICE'}
  proof=protected_entry({'entry':payload},matches[0],stops,'LONG','0.002')
  if proof.get('verified') is not True:raise ValueError('SIM_PROTECTED_STOP_UNVERIFIED')
  # The *real* production worker expects ETH quantity 0.001, so this is
  # explicitly a SIM adaptation (not an unmodified live exchange readback).
  mapped={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE',
    'clientOrderId':PROD_CLIENT,'symbol':'ETHUSDT','quantity':'0.001',
    'entryOrderId':str(matches[0]['orderId']),
    'positionId':str(p['id']),'stopAlgoId':str(stop['algoId'])}
  return mapped,p,stop
 try:
  proof,p,stop=exact_observation()
  root.mkdir(parents=True,exist_ok=True)
  (root/'weex_live_worker.py').write_bytes((ROOT/'weex_live_worker.py').read_bytes())
  # One-time incident reservation precedes starting the independent tick.
  claim=root/'weex_sim_supervisor_once.json'
  with claim.open('x',encoding='utf-8') as f:
   json.dump({'status':'SUPERVISOR_OUTCOME_UNKNOWN','clientId':m['clientId'],
     'entryOrderId':m['entryOrderId'],'supervisorPid':os.getpid()},f)
  def observer(_):
   events.append('independent_authenticated_sim_observation')
   exact_observation()
   return {'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'}
  def prepare(_):
   events.append('verified_exact_demo_close_proposal')
   return {'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'}
  def launcher():
   events.append('spawn_real_production_worker_get_only_cli')
   return subprocess.Popen([sys.executable,
       '-B','-c',CHILD_CODE,str(ROOT/'weex_live_worker.py'),json.dumps(proof)],
       cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  def recover_real(_):
   events.append('real_recover_v8')
   return recover(root,unknown_reader=lambda:True,proof_reader=lambda:proof,
     control_check=lambda:('STOPPED',True),launcher=launcher)
  def permission(_):
   events.append('SIM_ONLY_CLOSE_PERMISSION')
   return {'canClose':True}
  close_receipt={}
  def exit_exact(_):
   events.append('independent_sim_close_once')
   # Do NOT send if the restart's correctness cannot be proven. Failure
   # here leaves an already attached protective stop; no repeat close.
   if not (root/'weex_supervised_worker_restart_v8_latest.json').exists():
    return {'status':'WORKER_RECOVERY_NOT_ATTESTED','verifiedFlat':False}
   rr=json.loads((root/'weex_supervised_worker_restart_v8_latest.json').read_text(encoding='utf-8'))
   if rr.get('workerRestartConfirmed') is not True:
    return {'status':'WORKER_RECOVERY_NOT_ATTESTED','verifiedFlat':False}
   fresh,p,stop=exact_observation()
   if fresh!=proof:raise PermissionError('EXCHANGE_IDS_CHANGED')
   close={'symbol':'ETHUSDT','positionId':int(p['id'])}
   session.close_payload=close
   close_reserved=root/'weex_sim_close_outcome_unknown_v36.json'
   with close_reserved.open('x',encoding='utf-8') as f:
    json.dump({'status':'CLOSE_OUTCOME_UNKNOWN','close':close},f)
   ack=api.rest_api.execute_operation('post_capi_v3_closePositions',{'body':close}).data
   good=isinstance(ack,list) and len(ack)==1 and ack[0].get('success') is True and str(ack[0].get('positionId'))==str(close['positionId'])
   close_receipt.update(closePosts=1,closeAcknowledged=good,
                       closeOrderId=str(ack[0].get('successOrderId')) if good else None)
   remaining=[get('get_capi_v3_account_position_allPosition'),
              get('get_capi_v3_openOrders'),get('get_capi_v3_openAlgoOrders')]
   flat=all(x==[] for x in remaining)
   close_receipt['flatReadback']=flat
   close_receipt['remaining']={'positions':len(remaining[0]),
       'orders':len(remaining[1]),'algos':len(remaining[2])}
   return {'status':'CLOSE_VERIFIED_BY_INDEPENDENT_GET' if good and flat else
           'CLOSE_READBACK_UNCERTAIN','verifiedFlat':bool(good and flat)}
  msg=tick(root,observer=observer,recovery_planner=prepare,
     worker_recovery=recover_real,exit_policy_reader=permission,exit_executor=exit_exact)
  result={'status':'INDEPENDENT_SIM_SUPERVISOR_RECOVERY_EXIT_PASS' if
     msg.get('workerRestartConfirmed') is True and
     msg.get('exitPolicyResult')=='CLOSE_VERIFIED_BY_INDEPENDENT_GET' else
     'INDEPENDENT_SIM_SUPERVISOR_INCOMPLETE',
    'supervisorPid':os.getpid(),'workerRestartResult':msg.get('workerRestartResult'),
    'workerRestartConfirmed':msg.get('workerRestartConfirmed'),
    'exitPolicyResult':msg.get('exitPolicyResult'),
    'close':close_receipt,'events':events,
    'host':HOST,'simEntryPostsBySupervisor':0,
    'simClosePostsBySupervisor':session.calls,'productionPosts':0,
    'workerReaderAdapter':'EXACT_AUTHENTICATED_SIM_PROOF_MAPPED_FOR_PRODUCTION_CLI',
    'productionExitEndpointUsed':False,'exitEndpoint':'post_capi_v3_closePositions',
    'demoPermissionOnly':True,'liveGoCertified':False}
  (root/'weex_sim_supervisor_v36_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
  return result
 finally:session.shutdown()
if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('REQUIRE_ISOLATED_ROOT_AND_MANIFEST')
 try:print(json.dumps(execute(sys.argv[1],sys.argv[2]),ensure_ascii=False))
 except Exception as exc:
  print(json.dumps({'status':'INDEPENDENT_SIM_SUPERVISOR_BLOCKED',
    'errorType':type(exc).__name__,'productionPosts':0},ensure_ascii=False))
  raise SystemExit(3)
