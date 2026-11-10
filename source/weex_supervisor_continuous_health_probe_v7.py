"""Check a real independent monitor PID and heartbeat advance; no exchange writes."""
import json,time
from pathlib import Path
from weex_supervised_crash_entry_child_v5 import process_alive
from weex_supervised_exit_policy_v7 import status as exit_policy_status
ROOT=Path(__file__).resolve().parent
p=ROOT/'weex_supervised_crash_supervisor_health.json'
a=json.loads(p.read_text(encoding='utf-8'))
time.sleep(7)
b=json.loads(p.read_text(encoding='utf-8'))
valid=(b.get('status')=='OBSERVING_NOT_ARMED' and b.get('pid')==a.get('pid')
 and process_alive(int(b['pid'])) and b['heartbeatEpoch']>a['heartbeatEpoch']
 and 0<=time.time()-b['heartbeatEpoch']<=6
 and b.get('closeDispatchAllowed') is False and b.get('supportsExactReduceOnlyClose') is False
 and b.get('releaseCertified') is False)
print(json.dumps({'status':'CONTINUOUS_MONITOR_HEARTBEAT_PASS' if valid else 'CONTINUOUS_MONITOR_HEARTBEAT_FAIL',
 'pid':b.get('pid'),'heartbeatAdvanced':b.get('heartbeatEpoch',0)>a.get('heartbeatEpoch',0),
 'sameIndependentPid':b.get('pid')==a.get('pid'),
 'secondsBetween':round(b.get('heartbeatEpoch',0)-a.get('heartbeatEpoch',0),2),
 'exactExitPolicyArmed':exit_policy_status(ROOT).get('canClose') is True,
 'entryWritesAllowed':False,'releaseCertified':False}))
if not valid:raise SystemExit(2)
