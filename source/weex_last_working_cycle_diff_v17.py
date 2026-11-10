from pathlib import Path
import json,collections
r=Path(__file__).resolve().parent
p=r/'weex_live_worker_events.jsonl'
rows=[]
for line in p.open(encoding='utf-8'):
 try:rows.append(json.loads(line))
 except (ValueError,TypeError):pass
interesting=[x for x in rows if x.get('status') in ('OPENED_PROTECTED','BLOCKED_AFTER_ENTRY','BLOCKED_AFTER_DISPATCH','BLOCKED_RELEASE')]
for d in interesting[-40:]:
 print('EVENT',{k:d.get(k) for k in ('checkedAt','status','reason','control','opened','entryAttempts','recovered','releaseErrors') if k in d})
for day in ('2026-11-05','2026-11-06','2026-11-07','2026-11-08','2026-11-09','2026-11-10'):
 dayrows=[x for x in rows if str(x.get('checkedAt','')).startswith(day)]
 print('DAY',day,'count',len(dayrows),'statuses',collections.Counter(x.get('status') for x in dayrows).most_common(12))
print('RECENT_TRADING',[(x.get('checkedAt'),x.get('status')) for x in rows if x.get('status')=='OPENED_PROTECTED'][-14:])
for name in ('weex_ai_risk_config.before_gross_tp20.json','live_release_manifest.before_gross_tp20_20261105.json','live_release_manifest.before_supervised_worker_20261109.json'):
 p=r/name
 if not p.exists():continue
 try:
  d=json.loads(p.read_text(encoding='utf-8'))
  print('BACKUP',name,{'shaCount':len(d.get('sha256',{})),'execution':d.get('execution'), 'risk':{k:d.get('risk',{}).get(k) for k in ('minimumLeverage','orderCostTargetUSDT','stopLoss','marginModePreference')},'liveGoCertified':d.get('liveGoCertified')})
 except Exception as e:print('ERROR',name,type(e).__name__)
