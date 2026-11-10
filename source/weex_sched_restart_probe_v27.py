"""Isolated Windows Task Scheduler fail/restart probe, no WEEX imports."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,sys
root=Path(__file__).resolve().parent
state=root/'weex_sched_restart_probe_v27_state.json'
record={'at':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'parentPid':os.getppid(),'argv':sys.argv[1:]}
try:
 old=json.loads(state.read_text(encoding='utf-8'))
except (OSError,ValueError):old={'runs':[]}
old['runs'].append(record)
tmp=state.with_suffix('.tmp');tmp.write_text(json.dumps(old,indent=2),encoding='utf-8');tmp.replace(state)
if len(old['runs'])==1:
 raise SystemExit(23)
raise SystemExit(0)
