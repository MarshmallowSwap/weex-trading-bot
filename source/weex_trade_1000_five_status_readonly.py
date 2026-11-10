"""Investigate the five non-FILLED WEEX orders, GET-only and bounded."""
import json
from pathlib import Path
from decimal import Decimal as D
from monitor import query
from weex_api_budget import budget
ROOT=Path(__file__).resolve().parent
ck=json.loads((ROOT/'weex_trade_1000_economics_checkpoint.json').read_text())['orders']
trades=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text())['trades']
failed=[oid for oid,v in ck.items() if not v.get('verified')]
if len(failed)>5:raise ValueError('TOO_MANY_READS')
if budget().used()['weight']>=470:raise PermissionError('INSUFFICIENT_API_HEADROOM')
out=[]
for oid in failed:
 fills=[x for x in trades if str(x['orderId'])==oid]
 try:
  order=query('/capi/v3/order?orderId='+oid)
  out.append({'orderId':oid,'symbol':order.get('symbol'),'status':order.get('status'),
   'type':order.get('type'),'origQty':order.get('origQty'),
   'executedQty':order.get('executedQty'),'cumQuote':order.get('cumQuote'),
   'fillCountSnapshot':len(fills),
   'fillQuantitySnapshot':str(sum((D(str(x['qty'])) for x in fills),D(0))),
   'fillNotionalSnapshot':str(sum((D(str(x['quoteQty'])) for x in fills),D(0)))})
 except Exception as e:
  out.append({'orderId':oid,'errorClass':type(e).__name__})
  if type(e).__name__=='BudgetDeferred':break
p=ROOT/'weex_trade_1000_five_order_status_latest.json'
p.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
