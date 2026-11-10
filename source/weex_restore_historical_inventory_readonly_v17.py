from pathlib import Path
import json,datetime
r=Path(__file__).resolve().parent
files=sorted((p for p in r.iterdir() if p.is_file() and any(k in p.name.lower() for k in ('2026110','restore','backup','rollback','manifest','release','status','worker','control','live_'))),key=lambda x:x.stat().st_mtime)
print('TOTAL',len(files))
for p in files[-100:]:
 print(datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%m-%d %H:%M'),p.name)
for name in ('live_control.json','live_release_manifest.json','weex_ai_risk_config.json','weex_live_worker_latest.json','weex_final_live_status_latest.json'):
 p=r/name
 if p.is_file():
  try:
   data=json.loads(p.read_text(encoding='utf-8'))
   print('STRUCT',name,list(data.keys()) if isinstance(data,dict) else type(data).__name__)
   if name=='weex_ai_risk_config.json':
    print('CONFIG',{k:data.get(k) for k in ('environment','execution','risk','telegramSettings')})
   if name=='weex_live_worker_latest.json':
    print('LATEST',{k:data.get(k) for k in ('checkedAt','status','control','reason','tradingMode')})
  except Exception as exc:print('ERROR',name,type(exc).__name__)
