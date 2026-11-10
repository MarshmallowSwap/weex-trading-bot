"""No-network interactive task restart/relaunch probe (V29)."""
from pathlib import Path
from datetime import datetime,timezone
import json,os
root=Path(__file__).resolve().parent
file=root/'weex_sched_repeat_probe_v29_state.json'
try: state=json.loads(file.read_text(encoding='utf-8'))
except (OSError,ValueError):state={'runs':[]}
state['runs'].append({'at':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'parentPid':os.getppid()})
tmp=file.with_suffix('.tmp')
tmp.write_text(json.dumps(state,indent=2),encoding='utf-8')
tmp.replace(file)
raise SystemExit(23 if len(state['runs'])==1 else 0)
