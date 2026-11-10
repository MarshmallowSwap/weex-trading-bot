"""GET-free Windows supervisor runtime and scheduler correlation."""
import json,subprocess,os,time
from pathlib import Path
from weex_supervised_crash_entry_child_v5 import process_alive
root=Path(__file__).resolve().parent
p=root/'weex_supervised_crash_supervisor_health.json'
try:
 h=json.loads(p.read_text(encoding='utf-8'))
 pid=h.get('pid')
 print('HEALTH',json.dumps({'pid':pid,'ageSeconds':round(time.time()-h['heartbeatEpoch'],2),
  'alive':process_alive(pid),'status':h.get('status'),'pollInProgress':h.get('pollInProgress'),
  'entryDispatchAllowed':h.get('entryDispatchAllowed'),
  'closeDispatchAllowed':h.get('closeDispatchAllowed')}))
except Exception as e:print('HEALTH_ERROR',type(e).__name__)
ps=r"""Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'weex_supervised_process_monitor_v6.py' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"""
p=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=15)
print('LIVE_MONITOR_PROCESSES',p.stdout[:1800])
print('SCHEDULER_CODE_0x800710E0','TASK_OPERATOR_OR_ADMINISTRATOR_REFUSED_REQUEST')
