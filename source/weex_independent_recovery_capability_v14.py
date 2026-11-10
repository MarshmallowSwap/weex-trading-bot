"""GET/local-only capabilities audit. Never grants live permission or trades."""
import json,os,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
from weex_supervised_crash_entry_child_v5 import process_alive
from weex_supervised_exit_policy_v7 import status as exit_status
from weex_supervised_crash_watchdog_v4 import has_unknown_entry
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_http_guard import prepare_sdk_request
import live_control
ROOT=Path(__file__).resolve().parent
TASK='WEEX_Supervised_Incident_Noninteractive_V10'
def check(root=ROOT,*,task_xml=None,health=None,liveness=process_alive,headroom=None):
 root=Path(root);blockers=[]
 if health is None:
  try:health=json.loads((root/'weex_supervised_crash_supervisor_health.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):health={}
 if task_xml is None:
  try:
   flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
   p=subprocess.run(['schtasks','/Query','/TN',TASK,'/XML'],
    capture_output=True,text=True,timeout=8,creationflags=flags)
   task_xml=p.stdout if p.returncode==0 else ''
  except (OSError,subprocess.TimeoutExpired):task_xml=''
 try:
  x=ET.fromstring(task_xml)
  ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
  logon=x.findtext('.//t:LogonType',namespaces=ns)
  action=x.findtext('.//t:Actions/t:Exec/t:Arguments',namespaces=ns) or ''
  restart=x.find('.//t:RestartOnFailure',namespaces=ns) is not None
  task_ok=(logon=='S4U' and 'weex_supervised_process_monitor_v6.py' in action and restart)
 except (ET.ParseError,TypeError):task_ok=False
 if not task_ok:blockers.append('INDEPENDENT_S4U_TASK_NOT_VERIFIED')
 pid=health.get('pid')
 try:
  heartbeat_ok=(type(pid) is int and pid>0 and liveness(pid)
   and health.get('status')=='OBSERVING_NOT_ARMED'
   and 0<=time.time()-float(health.get('heartbeatEpoch',0))<=9
   and health.get('entryDispatchAllowed') is False
   and health.get('closeDispatchAllowed') is False)
 except (ValueError,TypeError,OSError):heartbeat_ok=False
 if not heartbeat_ok:blockers.append('LIVE_SUPERVISOR_HEARTBEAT_UNVERIFIED')
 try:
  control_ok=(live_control.state(root)['mode']=='STOPPED'
              and not live_control.build_errors(root))
 except Exception:control_ok=False
 if not control_ok:blockers.append('PRODUCTION_CONTROL_INTEGRITY_UNVERIFIED')
 close={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
        'type':'MARKET','quantity':'0.001',
        'newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
        'reduceOnly':True}
 try:
  q=prepare_sdk_request('post_capi_v3_order',close)
  sdk_ok=(q.get('state')=='STOPPED_BEFORE_NETWORK' and
          q.get('networkRequests')==0 and
          q.get('sdkSerializationVerified') is True)
 except Exception:sdk_ok=False
 if not sdk_ok:blockers.append('EXACT_REDUCEONLY_SDK_UNVERIFIED')
 try:permit=exit_status(root).get('canClose') is True
 except Exception:permit=False
 if not permit:blockers.append('INDEPENDENT_ONE_SHOT_EXIT_PERMIT_MISSING')
 try:unknown=has_unknown_entry(root,CLIENT_ID) is True
 except Exception:unknown=False
 if not unknown:blockers.append('REAL_WORKER_UNKNOWN_JOURNAL_MISSING')
 try:
  if headroom is None:
   from weex_api_budget import Budget
   headroom=lambda: Budget(root).require_supervised_recovery_headroom(preflight_weight=100)
  api_ok=headroom() is True
 except Exception:api_ok=False
 if not api_ok:blockers.append('API_RECOVERY_HEADROOM_UNVERIFIED')
 return {'status':'INDEPENDENT_CAPABILITIES_REVIEWED_NOT_ARMED',
  'taskS4UVerified':task_ok,'supervisorHeartbeatLive':heartbeat_ok,
  'productionIntegrityPass':control_ok,'reduceOnlySdkPreviewPass':sdk_ok,
  'exitPermitActive':permit,'realUnknownEntryPresent':unknown,
  'apiHeadroomReady':api_ok,'blockers':blockers,'entryDispatchAllowed':False,
  'closeDispatchAllowed':False,'releaseCertified':False,'exchangeWrites':0}
if __name__=='__main__':
 result=check()
 (ROOT/'weex_independent_recovery_capability_v14_latest.json').write_text(
  json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False))
