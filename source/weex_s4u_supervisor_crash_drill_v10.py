"""Controlled S4U supervisor crash; NO WEEX order writes.

Verifies independent S4U scheduled task identity, kills only task's current
monitor PID and checks respawn. Restores S4U task manually if auto restart
fails. Old interactive monitor remains disabled to avoid duplicate workers.
"""
import json,os,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
from weex_supervised_crash_entry_child_v5 import process_alive
ROOT=Path(__file__).resolve().parent
TASK='WEEX_Supervised_Incident_Noninteractive_V10'
HEALTH=ROOT/'weex_supervised_crash_supervisor_health.json'
REPORT=ROOT/'weex_s4u_supervisor_crash_drill_v10.json'
def save(r):
 t=REPORT.with_name(REPORT.name+'.tmp')
 t.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 os.replace(t,REPORT)
 print(json.dumps(r,ensure_ascii=False),flush=True)
def read():
 try:return json.loads(HEALTH.read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}
def valid(h):
 pid=h.get('pid')
 return (type(pid) is int and pid>0 and process_alive(pid)
  and h.get('status')=='OBSERVING_NOT_ARMED'
  and h.get('entryDispatchAllowed') is False
  and h.get('closeDispatchAllowed') is False
  and h.get('releaseCertified') is False
  and 0<=time.time()-h.get('heartbeatEpoch',0)<=7)
def cmd(*args):
 return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
  text=True,timeout=15)
def main():
 import live_control
 from weex_live_worker import Reader
 if live_control.state(ROOT).get('mode')!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('PRODUCTION_NOT_STOPPED')
 p,o,a=Reader(ROOT).account()
 if p or o or a:raise PermissionError('ACCOUNT_NOT_FLAT')
 taskxml=cmd('schtasks','/Query','/TN',TASK,'/XML')
 if taskxml.returncode!=0:raise PermissionError('S4U_TASK_NOT_INSTALLED')
 doc=ET.fromstring(taskxml.stdout)
 ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
 logon=doc.findtext('.//t:LogonType',namespaces=ns)
 action=doc.findtext('.//t:Actions/t:Exec/t:Arguments',namespaces=ns) or ''
 if logon!='S4U' or 'weex_supervised_process_monitor_v6.py' not in action:
  raise PermissionError('S4U_TASK_IDENTITY_UNVERIFIED')
 old=read()
 if not valid(old):raise PermissionError('S4U_HEARTBEAT_UNVERIFIED')
 pid=old['pid']
 report={'status':'CONTROLLED_S4U_KILL_REQUESTED','beforePid':pid,
  's4uIdentityVerified':True,'accountFlatBefore':True,'productionOrdersSent':0,
  'releaseGateChanged':False,'autoRestartVerified':False,'fallbackUsed':False}
 save(report)
 kill=cmd('taskkill','/PID',str(pid),'/F')
 report['killExitCode']=kill.returncode
 if kill.returncode!=0:
  report['status']='S4U_KILL_FAILED';save(report);raise SystemExit(2)
 newpid=None
 for _ in range(78):
  h=read()
  if h.get('pid')!=pid and valid(h):
   newpid=h['pid'];break
  time.sleep(1)
 if newpid:
  report.update(status='S4U_AUTOMATIC_RESTART_PASS',afterPid=newpid,
    autoRestartVerified=True)
 else:
  report.update(status='S4U_AUTORESTART_TIMEOUT_STARTING_FALLBACK',
    fallbackUsed=True)
  save(report)
  manual=cmd('schtasks','/Run','/TN',TASK)
  report['fallbackExitCode']=manual.returncode
  for _ in range(30):
   h=read()
   if h.get('pid')!=pid and valid(h):
    newpid=h['pid'];break
   time.sleep(1)
  report.update(status='S4U_FALLBACK_RECOVERED' if newpid else
    'S4U_RESTORE_FAILED',afterPid=newpid)
 if newpid:
  time.sleep(3)
  h=read()
  if h.get('pid')!=newpid or not valid(h):
   report['status']='S4U_RESTART_HEARTBEAT_NOT_STABLE'
 report['finishedEpoch']=time.time()
 save(report)
 if report['status']!='S4U_AUTOMATIC_RESTART_PASS':raise SystemExit(3)
if __name__=='__main__':main()
