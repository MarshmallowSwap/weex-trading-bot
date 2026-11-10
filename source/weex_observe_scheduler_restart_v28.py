import json,time,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent/'weex_sched_restart_probe_v27_state.json'
deadline=time.monotonic()+100
while time.monotonic()<deadline:
 try:d=json.loads(p.read_text(encoding='utf-8'))
 except (ValueError,OSError):d={'runs':[]}
 if len(d['runs'])>=2:
  out={'status':'SCHEDULER_AUTOMATIC_RESTART_OBSERVED','runs':d['runs'],
       'distinctPids':len({x['pid'] for x in d['runs']})>=2,
       'differentTimes':len({x['at'] for x in d['runs']})>=2}
  print(json.dumps(out));break
 time.sleep(2)
else:
 print(json.dumps({'status':'SCHEDULER_RESTART_NOT_OBSERVED','observedRuns':d.get('runs',[])}))
