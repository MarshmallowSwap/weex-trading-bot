"""Read-only cross-check actual WEEX POST telemetry vs worker/lifecycle. No secrets."""
from pathlib import Path
from contextlib import closing
import sqlite3,json,datetime,time
r=Path(__file__).resolve().parent
b=r/'weex_api_budget.sqlite3';life=r/'weex_user_live_lifecycle.sqlite3'
with closing(sqlite3.connect('file:'+b.resolve().as_posix()+'?mode=ro',uri=True)) as c:
 c.execute('PRAGMA query_only=ON')
 posts=c.execute("SELECT at,orders,path FROM api_calls_v1 WHERE orders>0 AND at>? ORDER BY at",(time.time()-7200,)).fetchall()
print('POST_QUOTA_COUNT',len(posts),'RECENT_10',[(datetime.datetime.fromtimestamp(x[0],datetime.timezone.utc).isoformat(),x[2]) for x in posts[-10:]])
with closing(sqlite3.connect('file:'+life.resolve().as_posix()+'?mode=ro',uri=True)) as c:
 c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
 schema=c.execute('PRAGMA table_info(writes_v1)').fetchall()
 print('LIFECYCLE_WRITE_COLUMNS',[x['name'] for x in schema])
 rows=c.execute('SELECT * FROM writes_v1 ORDER BY rowid DESC LIMIT 5').fetchall()
 print('LAST_WRITES',[{'trade_id':x['trade_id'],'kind':x['kind'],'state':x['state']} for x in rows])
p=r/'weex_live_worker_events.jsonl'
if p.exists():
 matches=[]
 for line in p.open(encoding='utf-8'):
  try:d=json.loads(line)
  except ValueError:continue
  checked=str(d.get('checkedAt',''))
  if checked.startswith('2026-11-10T09:0') or checked.startswith('2026-11-10T08:4'):
   matches.append({'at':checked,'status':d.get('status'),'openedCount':len(d.get('opened') or []),
    'entryAttempts':len(d.get('entryAttempts') or [])})
 print('WORKER_AT_POSTS',matches[-16:])
