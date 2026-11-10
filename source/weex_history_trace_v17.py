from pathlib import Path
import json,datetime,collections
r=Path(__file__).resolve().parent
for p in sorted(r.iterdir(),key=lambda x:x.stat().st_mtime):
 if not p.is_file():continue
 n=p.name.lower()
 if p.stat().st_mtime >= datetime.datetime(2026,11,9).timestamp():continue
 if any(s in n for s in ('live','release','control','worker','restart','tp','backup','state','collaudo','activation','manifest','rollback','restore','gate')):
  if p.suffix.lower() in ('.json','.md','.bak','.py','.zip','.txt'):
   print('ARCH',datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%m-%d %H:%M'),p.name)
print('==== LOG TIMELINE ====')
for logname in ('weex_live_worker_events.jsonl','weex_live_control_history.jsonl','weex_live_control_events.jsonl'):
 p=r/logname
 if not p.is_file():continue
 rows=[]
 for line in p.open(encoding='utf-8'):
  try:
   d=json.loads(line)
   rows.append({k:d.get(k) for k in ('checkedAt','changed','status','reason','mode','generation')})
  except Exception:continue
 print('LOG',logname,'count',len(rows),'first',rows[:4],'last',rows[-12:])
 group=collections.Counter(str(x.get('status')) for x in rows)
 print('COUNTS',group.most_common(18))
print('==== BACKUPS and CONTROL ====')
for name in ('live_control_state.json','live_control.json','weex_live_control.json','live_release_gate_latest.json','weex_recovery_manifest_latest.json'):
 p=r/name
 if p.is_file():
  try:
   d=json.loads(p.read_text(encoding='utf-8'))
   print('FILE',name,{k:d.get(k) for k in ('mode','status','passed','total','blockers','changed','generation','go','reason') if k in d})
  except Exception: pass
