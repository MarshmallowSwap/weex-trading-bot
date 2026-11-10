"""Inspect local WEEX API request-weight ledger; never contacts exchange."""
import json,sqlite3,time
from contextlib import closing
from pathlib import Path
from weex_api_budget import Budget
ROOT=Path(__file__).resolve().parent
used=Budget(ROOT).used()
with closing(sqlite3.connect(ROOT/'weex_api_budget.sqlite3')) as c:
 current=time.time()
 rows=c.execute('SELECT path,COUNT(*),SUM(weight) FROM api_calls_v1 WHERE at>? GROUP BY path ORDER BY SUM(weight) DESC',(current-600,)).fetchall()
 oldest=c.execute('SELECT MIN(at),MAX(at) FROM api_calls_v1 WHERE at>?',(current-600,)).fetchone()
 limits=used['limits']
 long_limits=[x['limit'] for x in limits if x['type']=='REQUEST_WEIGHT' and x['windowSeconds']>=600]
 long_limit=min(long_limits) if long_limits else None
 recovery_reserve=150
 preflight_reserve=100
 remaining=long_limit-used['weight'] if long_limit is not None else None
 print(json.dumps({'windowSeconds':600,'weightUsed':used['weight'],
   'orderPostsCount':used['orders'],'cooldownActive':used['pauseUntil']>current,
   'serverLongWindowSafetyLimit':long_limit,
   'recoveryReserveWeight':recovery_reserve,'preflightReserveWeight':preflight_reserve,
   'longWindowRemainingWeight':remaining,
   'preflightLongWindowFits':remaining is not None and remaining>=recovery_reserve+preflight_reserve,
   'recoveryOnlyLongWindowFits':remaining is not None and remaining>=recovery_reserve,
   'note':'Actual admission also checks shorter windows, order limits and server counters',
   'pathWeights':[{'path':p,'calls':n,'weight':w} for p,n,w in rows],
   'minAgeSeconds':round(current-oldest[0],1) if oldest[0] else None,
   'exchangeRequestsByThisScript':0}))
