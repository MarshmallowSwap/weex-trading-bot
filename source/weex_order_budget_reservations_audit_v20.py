import sqlite3,json,datetime,time
from pathlib import Path
from contextlib import closing
root=Path(__file__).resolve().parent
with closing(sqlite3.connect('file:'+(root/'weex_api_budget.sqlite3').resolve().as_posix()+'?mode=ro',uri=True)) as c:
 c.execute('PRAGMA query_only=ON')
 rows=c.execute("SELECT at,weight,orders,path FROM api_calls_v1 WHERE orders>0 AND at>? ORDER BY at DESC LIMIT 10",(time.time()-3600,)).fetchall()
 notes=c.execute("SELECT at,status,path,headers FROM api_server_observations_v1 WHERE path='/capi/v3/order' AND at>? ORDER BY at DESC LIMIT 10",(time.time()-3600,)).fetchall()
print(json.dumps({'orderQuotaReservations':[{'utc':datetime.datetime.fromtimestamp(r[0],datetime.timezone.utc).isoformat(),'weight':r[1],'orders':r[2],'path':r[3]} for r in rows],'serverResponses':[{'utc':datetime.datetime.fromtimestamp(r[0],datetime.timezone.utc).isoformat(),'status':r[1],'path':r[2]} for r in notes],'exchangeRequestsByThisScript':0}))
