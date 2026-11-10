"""Observe a scheduled task fail and relaunch; never launch the task ourselves."""
import json,time,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent
p=root/'weex_sched_repeat_probe_v29_state.json'
deadline=time.monotonic()+145
last=0
while time.monotonic()<deadline:
 try: state=json.loads(p.read_text(encoding='utf-8'))
 except (OSError,ValueError):state={'runs':[]}
 if len(state['runs'])!=last:
  last=len(state['runs'])
  print('RUNS',json.dumps(state,ensure_ascii=False),flush=True)
 if len(state['runs'])>=2:
  print('RESULT',json.dumps({'status':'AUTOMATIC_SCHEDULED_RELAUNCH_VERIFIED',
   'differentPids':len({x['pid'] for x in state['runs']})>1,'runs':state['runs']},ensure_ascii=False),flush=True)
  break
 time.sleep(2)
else:print('RESULT',json.dumps({'status':'NO_AUTOMATIC_SCHEDULED_RELAUNCH_OBSERVED',
  'runs':state.get('runs',[])}),flush=True)
