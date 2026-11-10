"""Read-only triage of three one-fill parent quote contradictions.

No attempts to infer missing fills, no writes, preserve exact decimal
differences and parent exchange fields for escalation.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from monitor import query
from weex_api_budget import budget
import live_control
ROOT=Path(__file__).resolve().parent
if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
 raise PermissionError('PRODUCTION_MUST_BE_STOPPED')
if budget().used()['weight']>=455:raise PermissionError('API_QUOTA_HEADROOM_REQUIRED')
snapshot=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text())['trades']
scope=json.loads((ROOT/'weex_1000_parent_quote_mismatch_full_audit.json').read_text())['details']
targets=[x for x in scope if x['status']=='FILLED' and x['parentQuoteMismatch'] and x['distinctFillPrices']==1]
if len(targets)!=3:raise ValueError('EXPECTED_THREE_SINGLE_PRICE_EXCEPTIONS')
out=[]
for item in targets:
 oid=item['orderId']
 order=query('/capi/v3/order?orderId='+oid)
 matched=[f for f in snapshot if str(f['orderId'])==oid]
 if len(matched)!=1:raise ValueError('NOT_SINGLE_FILL')
 f=matched[0]
 qty=D(str(f['qty']));price=D(str(f['price']));quote=D(str(f['quoteQty']))
 executed=D(str(order['executedQty']));avg=D(str(order['avgPrice']));cum=D(str(order['cumQuote']))
 out.append({'orderId':oid,'symbol':item['symbol'],'orderStatus':order.get('status'),
  'fillQuantity':str(qty),'parentExecutedQty':str(executed),
  'fillPrice':str(price),'parentAvgPrice':str(avg),
  'fillNotional':str(quote),'parentCumQuote':str(cum),
  'parentAvgPriceTimesQty':str(avg*qty),
  'parentQuoteMinusFillQuote':str(cum-quote),
  'parentAvgMinusFillPrice':str(avg-price),
  'fillPriceTimesQty':str(price*qty),
  'quantityMatches':qty==executed,
  'quoteMatchesFillArithmetic':quote==qty*price,
  'parentFieldsMatchFill':avg==price and cum==quote})
result={'checkedAt':datetime.now(timezone.utc).isoformat(),'ordersAudited':len(out),
 'parentFieldsConflicting':sum(not x['parentFieldsMatchFill'] for x in out),
 'exchangeWrites':0,'scope':'THREE_ONE_FILL_EXCEPTIONS','details':out}
p=ROOT/'weex_1000_three_single_fill_parent_quote_readback.json';t=p.with_suffix('.tmp')
t.write_text(json.dumps(result,indent=2));os.replace(t,p)
print(json.dumps(result))
