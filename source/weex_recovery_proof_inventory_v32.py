from pathlib import Path
import json
r=Path(__file__).resolve().parent
for name in ('weex_demo_crash_recovery_20261109_result.json','weex_supervised_worker_restart_v8_latest.json','weex_supervised_crash_supervisor_health.json','weex_supervised_process_monitor_v6_latest.json','weex_sim_active_stop_close_trial_20261109_run2.json'):
 p=r/name
 if p.exists():
  try:
   d=json.loads(p.read_text(encoding='utf-8'))
   fields=('status','accountFlat','stopVerified','noDuplicateEntry','closeAcknowledged','workerRestartConfirmed','entryRetries','ordersSent','host','exitPolicyResult','incident','releaseCertified','pid')
   print(name,{k:d[k] for k in fields if k in d})
  except Exception as e:print(name,type(e).__name__)
 else:print(name,'ABSENT')
