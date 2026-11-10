"""Controlled Windows supervisor crash/restart exercise; NO exchange writes.

Only kill verified monitor Python PID while account state was observed FLAT.
Allow Windows Task Scheduler to auto-respawn. If it doesn't, manually
restart the existing read-only task to recover the monitor. Never arms trading.
"""
import json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HEALTH=ROOT/'weex_supervised_crash_supervisor_health.json'
REPORT=ROOT/'weex_supervisor_os_crash_test_20261110.json'
TASK='WEEX_Supervised_Incident_Readonly_V6'
def output(data):
 temporary=REPORT.with_suffix('.tmp')
 temporary.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 os.replace(temporary,REPORT)
 print(json.dumps(data,ensure_ascii=False),flush=True)
def process_command(pid):
 args=['powershell','-NoProfile','-Command',
       '(Get-CimInstance Win32_Process -Filter "ProcessId = '+str(pid)+'").CommandLine']
 r=subprocess.run(args,capture_output=True,text=True,timeout=12)
 return r.stdout.strip() if r.returncode==0 else ''
def get_health():
 try:return json.loads(HEALTH.read_text(encoding='utf-8'))
 except (ValueError,OSError):return {}
def current_ready(previous=None):
 h=get_health();pid=h.get('pid')
 if not isinstance(pid,int) or pid<=0 or pid==previous:return None
 if h.get('status')!='OBSERVING_NOT_ARMED' or h.get('entryDispatchAllowed') is not False:return None
 if not 0<=time.time()-float(h.get('heartbeatEpoch',0))<=9:return None
 command=process_command(pid)
 if 'weex_supervised_process_monitor_v6.py' not in command or '--loop' not in command:return None
 return pid
def main():
 import live_control
 s=live_control.state(ROOT)
 if s.get('mode')!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('PRODUCTION_MUST_BE_STOPPED_AND_INTEGRITY_CLEAR')
 from weex_live_worker import Reader
 rows=Reader(ROOT).account()
 if rows!=([],[],[]):
  raise PermissionError('ACCOUNT_NOT_EMPTY_FOR_OS_CRASH_TEST')
 before=current_ready()
 if not before:raise PermissionError('MONITOR_NOT_READY_FOR_CONTROLLED_TEST')
 r={'status':'TEST_STARTED','beforePid':before,'productionOrdersSent':0,
    'accountFlatBefore':True,'automaticRestartVerified':False,
    'manualFallbackUsed':False,'startedEpoch':time.time()}
 output(r)
 killed=subprocess.run(['taskkill','/PID',str(before),'/F'],capture_output=True,text=True,timeout=15)
 r['killExitCode']=killed.returncode
 if killed.returncode!=0:
  r['status']='KILL_FAILED';output(r);return
 r['status']='OS_MONITOR_TERMINATED_WAITING_FOR_SCHEDULER';output(r)
 replacement=None
 for _ in range(85):
  replacement=current_ready(before)
  if replacement:break
  time.sleep(1)
 if replacement:
  r.update(status='AUTOMATIC_SCHEDULER_RESTART_VERIFIED',
     afterPid=replacement,automaticRestartVerified=True)
 else:
  r['manualFallbackUsed']=True
  r['status']='AUTO_RESTART_NOT_OBSERVED_MANUAL_RECOVERY';output(r)
  restart=subprocess.run(['schtasks','/Run','/TN',TASK],capture_output=True,text=True,timeout=15)
  r['manualRestartExitCode']=restart.returncode
  for _ in range(25):
   replacement=current_ready(before)
   if replacement:break
   time.sleep(1)
  r.update(status='MANUAL_FALLBACK_RESTORED' if replacement else 'RESTORE_FAILED',
           afterPid=replacement)
 r['finishedEpoch']=time.time();output(r)
if __name__=='__main__':main()
