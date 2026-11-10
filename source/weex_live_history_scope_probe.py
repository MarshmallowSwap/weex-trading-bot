"""Scope-only inspection of exact WEEX bot entry times and recent symbol fills.
No credentials, full response bodies or personal account IDs in console output.
Read-only; catches 100-row truncation rather than treating it as complete.
"""
from weex_live_worker import Reader,ROOT
from weex_live_unresolved_local_evidence import local_records
from datetime import datetime,timezone
import json
def run():
 r=Reader(ROOT);data=[]
 for x in local_records():
  entry=r.read('get_capi_v3_order',orderId=x['entryOrderId'])
  start=int(entry['time'])
  end=int(datetime.now(timezone.utc).timestamp()*1000)
  fills=r.read('get_capi_v3_userTrades',symbol=x['symbol'],startTime=start-60000,endTime=end,limit=100)
  data.append({'symbol':x['symbol'],'entryAt':datetime.fromtimestamp(start/1000,timezone.utc).isoformat(),
   'returnedFills':len(fills),'hasLimitSaturation':len(fills)>=100,
   'sideCounts':{str(side):sum(z.get('side')==side for z in fills)
                 for side in sorted({z.get('side') for z in fills})},
   'reduceOnlyTypes':sorted({type(z.get('reduceOnly')).__name__ for z in fills}),
   'fields':sorted(set().union(*(set(z) for z in fills))) if fills else [],
   'firstFillAt':datetime.fromtimestamp(min(int(z['time']) for z in fills)/1000,timezone.utc).isoformat() if fills else None,
   'lastFillAt':datetime.fromtimestamp(max(int(z['time']) for z in fills)/1000,timezone.utc).isoformat() if fills else None})
 return {'source':'WEEX_LIVE_GET_ONLY','rows':data,'writes':0}
if __name__=='__main__':print(json.dumps(run()))
