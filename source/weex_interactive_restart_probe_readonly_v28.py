from pathlib import Path
import json,subprocess,time
r=Path(__file__).resolve().parent
p=r/'weex_sched_restart_probe_v27_state.json'
print('PROBE_STATE',p.read_text(encoding='utf-8') if p.exists() else 'NOT_CREATED')
s=subprocess.run(['schtasks','/Query','/TN','WEEX_Restart_Interactive_Probe_V28','/XML'],text=True,capture_output=True,timeout=10)
print('RESTART_CONFIGURED',s.returncode==0 and '<RestartOnFailure>' in s.stdout)
