"""Operational WEEX recovery controller prearm, no authority to send or grant.

This is NOT the live incident certifier. Fail closed against real independent
task, heartbeat, production build, SDK exit serialization, operator permit,
fresh all-symbol CROSS account and WEEX API reserve. A valid prearm does not
certify a real crash; it is only a prerequisite for future audited promotion.
"""
from __future__ import annotations
import json,os,time,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from weex_supervised_crash_entry_child_v5 import process_alive
from weex_supervised_exit_policy_v7 import status as exit_status
from weex_http_guard import prepare_sdk_request
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_account_observation import load
import live_control

ROOT=Path(__file__).resolve().parent
TASK='WEEX_Supervised_Incident_Noninteractive_V10'
HEALTH='weex_supervised_crash_supervisor_health.json'

def assess(*,task_xml,health,task_running,live_pid,integrity_pass,exit_permit,
           sdk_close,api_headroom,snapshot,now=None):
 now=time.time() if now is None else now
 blockers=[]
 try:
  xml=ET.fromstring(task_xml)
  ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
  logon=xml.findtext('.//t:LogonType',namespaces=ns)
  argument=xml.findtext('.//t:Actions/t:Exec/t:Arguments',namespaces=ns) or ''
  restart=xml.find('.//t:RestartOnFailure',namespaces=ns) is not None
  task_ok=logon=='S4U' and 'weex_supervised_process_monitor_v6.py' in argument and restart and task_running is True
 except (ET.ParseError,TypeError):task_ok=False
 if not task_ok:blockers.append('INDEPENDENT_S4U_MONITOR_TASK_UNVERIFIED')
 try:
  monitor_ok=(health.get('scope')=='ETH100_CRASH_PRODUCTION_WORKER_V5'
    and health.get('status')=='OBSERVING_NOT_ARMED'
    and live_pid is True and 0<=now-float(health.get('heartbeatEpoch'))<=8
    and health.get('entryDispatchAllowed') is False)
 except (ValueError,TypeError,AttributeError):monitor_ok=False
 if not monitor_ok:blockers.append('INDEPENDENT_MONITOR_HEARTBEAT_UNVERIFIED')
 if integrity_pass is not True:blockers.append('STOPPED_CODE_INTEGRITY_REQUIRED')
 if sdk_close is not True:blockers.append('EXACT_REDUCE_ONLY_CLOSE_PREVIEW_REQUIRED')
 if exit_permit is not True:blockers.append('INDEPENDENT_ONE_SHOT_EXIT_PERMIT_REQUIRED')
 if api_headroom is not True:blockers.append('WEEX_RECOVERY_API_HEADROOM_UNVERIFIED')
 snapshot_ok=False
 if isinstance(snapshot,dict):
  try:
   started=snapshot['startedAtMs']/1000
   completed=snapshot['completedAtMs']/1000
   snapshot_ok=(snapshot.get('complete') is True
     and 0<=now-started<=8 and 0<=completed-started<=5
     and all(isinstance(snapshot[k],list) for k in
      ('positions','regularOrders','conditionalOrders','trailingOrders')))
  except (KeyError,ValueError,TypeError):pass
 if not snapshot_ok:blockers.append('FRESH_COMPLETE_CROSS_SNAPSHOT_REQUIRED')
 elif any(snapshot[k] for k in ('positions','regularOrders','conditionalOrders','trailingOrders')):
  blockers.append('SHARED_CROSS_COLLATERAL_OCCUPIED')
 # Operational standby needs real restart and close-failure proofs.
 # Historical unit tests and SDK preview cannot replace them.
 blockers.append('INDEPENDENT_PROCESS_RESTART_AND_EXIT_DRILL_NOT_ATTESTED')
 return {'status':'OPERATIONAL_PREARM_BLOCKED' if blockers else 'OPERATIONAL_PREARM_CANDIDATE',
  'scope':'ETH100_CRASH_PRODUCTION_WORKER_V5','blockers':blockers,
  'taskVerified':task_ok,'monitorLive':monitor_ok,
  'accountFlatForNewCrossEntry':snapshot_ok and
     not any(snapshot[k] for k in ('positions','regularOrders','conditionalOrders','trailingOrders')),
  'exitPermissionGranted':exit_permit is True,
  'readyToRecover':False,'mayPublishReadyHeartbeat':False,
  'entryAllowed':False,'closeAllowed':False,
  'liveCrashCertified':False,'networkWrites':0}

def check(root=ROOT):
 root=Path(root);task_xml='';running=False
 try:
  flag=getattr(subprocess,'CREATE_NO_WINDOW',0)
  q=subprocess.run(['schtasks','/Query','/TN',TASK,'/XML'],
    capture_output=True,text=True,timeout=8,creationflags=flag)
  if q.returncode==0:task_xml=q.stdout
  running_task=subprocess.run(['schtasks','/Query','/TN',TASK,'/FO','LIST','/V'],
    capture_output=True,text=True,timeout=8,creationflags=flag)
  # Localized Windows output is not a trustworthy machine-readable task-state
  # proof; require S4U XML and live PID, but don't infer 'RUNNING' from text.
  running=running_task.returncode==0
 except (OSError,subprocess.TimeoutExpired):pass
 try:health=json.loads((root/HEALTH).read_text(encoding='utf-8'))
 except (OSError,ValueError):health={}
 pid=health.get('pid')
 live=isinstance(pid,int) and process_alive(pid)
 try:integrity=live_control.state(root)['mode']=='STOPPED' and not live_control.build_errors(root)
 except Exception:integrity=False
 payload={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',
          'quantity':'0.001','newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
          'reduceOnly':True}
 try:
  a=prepare_sdk_request('post_capi_v3_order',payload)
  sdk=a.get('state')=='STOPPED_BEFORE_NETWORK' and a.get('sdkSerializationVerified') is True and a.get('networkRequests')==0
 except Exception:sdk=False
 try:
  from weex_api_budget import Budget
  budget=Budget(root).require_supervised_recovery_headroom(preflight_weight=100) is True
 except Exception:budget=False
 snapshot=load(root,max_age=8)
 out=assess(task_xml=task_xml,health=health,task_running=running,
  live_pid=live,integrity_pass=integrity,exit_permit=exit_status(root).get('canClose') is True,
  sdk_close=sdk,api_headroom=budget,snapshot=snapshot)
 out['evidence']='REAL_LOCAL_TASK_AND_READONLY_ACCOUNT'
 return out

if __name__=='__main__':
 print(json.dumps(check(),ensure_ascii=False))
