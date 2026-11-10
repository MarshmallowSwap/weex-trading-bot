"""Local WEEX API budget snapshot, read-only SQLite."""
import sqlite3,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
with sqlite3.connect('file:'+(ROOT/'weex_api_budget.sqlite3').as_posix()+'?mode=ro',uri=True) as c:
    c.execute('PRAGMA query_only=ON')
    limits=c.execute('SELECT kind,seconds,limit_value FROM api_limits_v2').fetchall()
    calls=c.execute('SELECT path,COUNT(*),SUM(weight) FROM api_calls_v1 WHERE at>? GROUP BY path ORDER BY SUM(weight) DESC LIMIT 15',(time.time()-300,)).fetchall()
    counters=c.execute('SELECT kind,seconds,used,observed_at FROM api_counters_v2').fetchall()
print(json.dumps({'limits':limits,'recent5minCalls':calls,'counters':[{'kind':x[0],'window':x[1],'used':x[2],'ageSeconds':int(time.time()-x[3])} for x in counters]},ensure_ascii=False))
