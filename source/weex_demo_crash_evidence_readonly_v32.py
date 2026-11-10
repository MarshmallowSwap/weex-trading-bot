import json
from pathlib import Path
p=Path(__file__).resolve().parent/'weex_demo_crash_recovery_20261109_result.json'
d=json.loads(p.read_text(encoding='utf-8'))
allowed=('at','host','status','childExitCode','childState','observedEntries','positionCount','activeStops','regularOrders','stopVerified','exactEntryVerified','noDuplicateEntry','closeAcknowledged','accountFlat','remaining','retries','realOrders','demoEntryPOSTs','demoClosePOSTs')
print(json.dumps({k:d[k] for k in allowed if k in d},ensure_ascii=False,default=str))
