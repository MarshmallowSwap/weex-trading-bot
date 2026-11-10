import json,time,pathlib
p=pathlib.Path(__file__).resolve().parent/'weex_supervised_crash_supervisor_health.json'
for i in range(5):
 h=json.loads(p.read_text(encoding='utf-8'))
 print(json.dumps({'sample':i,'age':round(time.time()-h['heartbeatEpoch'],2),'pid':h.get('pid'),'inPoll':h.get('pollInProgress'),'time':time.time()}),flush=True)
 if i<4:time.sleep(3)
