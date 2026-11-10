"""Authenticate WEEX recent fills/orders near unexplained local POST telemetry.
GET-only; report timestamps/status, no credentials or payloads."""
from datetime import datetime,timezone
from monitor import query
from weex_order_pagination import history
import json
p=lambda n:datetime.fromtimestamp(float(n)/1000,timezone.utc).isoformat() if n else None
trades=query('/capi/v3/userTrades?limit=100')
orders=history(max_pages=5)
begin=int(datetime(2026,11,10,8,0,tzinfo=timezone.utc).timestamp()*1000)
end=int(datetime(2026,11,10,9,15,tzinfo=timezone.utc).timestamp()*1000)
matched=[]
for t in trades:
 try:
  at=int(t.get('time') or 0)
  if begin<=at<=end:matched.append({'at':p(at),'symbol':t.get('symbol'),'orderId':str(t.get('orderId'))})
 except (TypeError,ValueError):pass
recent=[]
for o in orders['orders']:
 try:
  at=int(o.get('time') or o.get('updateTime') or 0)
  if begin<=at<=end:recent.append({'at':p(at),'symbol':o.get('symbol'),'type':o.get('type'),'status':o.get('status')})
 except (TypeError,ValueError):pass
print(json.dumps({'source':'authenticated WEEX GET','fillCountInWindow':len(matched),'fillsInWindow':matched[:20],
'orderCountInWindow':len(recent),'ordersInWindow':recent[:20],
'historyCompleteWithinBounds':orders.get('completeWithinRequestedBounds'),'exchangeWrites':0},ensure_ascii=False))
