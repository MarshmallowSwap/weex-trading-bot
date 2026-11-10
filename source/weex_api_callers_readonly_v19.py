"""GET-free inspection of WEEX API spending patterns and local schedulers."""
from pathlib import Path
from collections import defaultdict
import sqlite3,time,json,datetime
from contextlib import closing
ROOT=Path(__file__).resolve().parent
path=ROOT/'weex_api_budget.sqlite3'
out={}
with closing(sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)) as c:
 c.execute('PRAGMA query_only=ON')
 for seconds in (60,180,600):
  cutoff=time.time()-seconds
  rows=c.execute('SELECT path,COUNT(*),SUM(weight) FROM api_calls_v1 WHERE at>? GROUP BY path ORDER BY SUM(weight) DESC',(cutoff,)).fetchall()
  out[str(seconds)+'Seconds']=[{'path':p,'count':n,'weight':w} for p,n,w in rows]
 for path in ('/capi/v3/market/klines','/capi/v3/market/depth','/capi/v3/account/position/allPosition'):
  values=c.execute('SELECT at FROM api_calls_v1 WHERE path=? AND at>? ORDER BY at DESC LIMIT 10',(path,time.time()-600)).fetchall()
  out['recent_'+path]=[datetime.datetime.fromtimestamp(v[0],datetime.timezone.utc).isoformat() for v in values]
print(json.dumps(out,ensure_ascii=False))
