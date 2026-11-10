"""Read-only verified QNT position economics from WEEX; no order placement."""
import json
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal as D
from weex_live_worker import Reader
from weex_reconcile import Reconciler
import live_control
root=Path(__file__).resolve().parent
r=Reconciler(root,Reader(root),live_control.state(root),lambda *a,**k:None,timeout=60)
item=r.engine.get('wxentry_7f327b721a398e3e86033c73')
ev=r.gather(item)
p=ev['proof']
def summary(o):
    k=('orderId','clientOrderId','symbol','side','positionSide','status','type','time','origQty','executedQty','avgPrice','cumQuote','reduceOnly')
    return {x:o.get(x) for x in k}
data={'positionSide':item['plan']['entry']['positionSide'],'targetNetProfitUSDT':item['plan'].get('targetNetProfitUSDT'),
      'entryCostUSDT':item['owned']['actualEntryCostUSDT'],'entryFeesUSDT':item['owned']['actualEntryFeesUSDT'],
      'entryQuantity':item['owned']['quantity'],'exitTrigger':item['owned']['tpRequest'].get('triggerPrice'),
      'orders':[summary(o) for o in ev['orders'] if D(str(o.get('executedQty') or 0))>0],
      'fills':{},'proof':p}
for k,rows in ev['fills'].items():
    d={'quantity':str(sum((D(str(x['qty'])) for x in rows),D(0))),
       'notional':str(sum((D(str(x['qty']))*D(str(x['price'])) for x in rows),D(0))),
       'feesUSDT':str(sum((D(str(x['commission'])) for x in rows),D(0))),
       'firstTimeMs':min(int(x['time']) for x in rows),'lastTimeMs':max(int(x['time']) for x in rows),
       'numberOfFills':len(rows)}
    d['vwap']=str(D(d['notional'])/D(d['quantity']))
    d['firstUTC']=datetime.fromtimestamp(d['firstTimeMs']/1000,timezone.utc).isoformat()
    d['lastUTC']=datetime.fromtimestamp(d['lastTimeMs']/1000,timezone.utc).isoformat()
    data['fills'][k]=d
print(json.dumps(data,indent=2))
