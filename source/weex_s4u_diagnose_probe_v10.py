import time,json,pathlib
from weex_supervised_crash_entry_child_v5 import process_alive
p=pathlib.Path(__file__).resolve().parent/'weex_supervised_crash_supervisor_health.json'
a=json.loads(p.read_text(encoding='utf-8'));time.sleep(7);b=json.loads(p.read_text(encoding='utf-8'))
d={'statusGood':b.get('status')=='OBSERVING_NOT_ARMED','pidSame':a.get('pid')==b.get('pid'),
 'alive':process_alive(int(b.get('pid',0))),
 'heartbeatAdvanced':b.get('heartbeatEpoch',0)>a.get('heartbeatEpoch',0),
 'heartbeatAge':round(time.time()-b.get('heartbeatEpoch',0),3),
 'disabledClose':b.get('closeDispatchAllowed') is False,
 'closeCapabilityFalse':b.get('supportsExactReduceOnlyClose') is False,
 'releaseFalse':b.get('releaseCertified') is False,
 'pid':b.get('pid'),
 'heartbeatDelta':round(b.get('heartbeatEpoch',0)-a.get('heartbeatEpoch',0),3)}
print(json.dumps(d),flush=True)
