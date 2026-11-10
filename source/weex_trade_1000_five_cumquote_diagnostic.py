"""Read-only WEEX diagnostic for exactly five audited canceled partial orders.
Compare parent cumQuote to fill sum and candidate qty * avgPrice.
Never interpret the parent quote as authoritative economics without evidence.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import datetime,timezone
from monitor import query
from weex_api_budget import budget
import live_control
R=Path(__file__).resolve().parent
if live_control.state(R)['mode']!='STOPPED' or live_control.build_errors(R):
    raise PermissionError('MAIN_MUST_BE_STOPPED')
if budget().used()['weight']>450:raise PermissionError('API_HEADROOM_REQUIRED')
orders=json.loads((R/'weex_trade_1000_partial_canceled_audit.json').read_text())['details']
allfills=json.loads((R/'weex_trade_1000_snapshot.json').read_text())['trades']
g=defaultdict(list)
for f in allfills:g[str(f['orderId'])].append(f)
results=[]
for row in orders:
 oid=row['orderId']
 try:
  order=query('/capi/v3/order?orderId='+oid)
  fills=g[oid]
  qty=sum((D(str(f['qty'])) for f in fills),D(0))
  quote=sum((D(str(f['quoteQty'])) for f in fills),D(0))
  fees=sum((D(str(f['commission'])) for f in fills),D(0))
  avg=D(str(order['avgPrice']));parent=D(str(order['cumQuote']))
  distinct=sorted({D(str(f['price'])) for f in fills})
  result={'orderId':oid,'symbol':order.get('symbol'),
    'status':order.get('status'),'originalQty':order.get('origQty'),
    'executedQty':order.get('executedQty'),
    'avgPrice':str(avg),'cumQuote':str(parent),
    'fillQuoteSum':str(quote),'fillQtySum':str(qty),'feesUSDT':str(fees),
    'avgTimesExecutedQty':str(avg*qty),
    'cumQuoteEqualsAvgTimesQty':parent==avg*qty,
    'avgMatchesOneFillPrice':avg in distinct,
    'numberOfDistinctFillPrices':len(distinct),
    'weightedFillAveragePrice':str(quote/qty),
    'parentQuoteDifference':str(parent-quote),
    'qtyMatches':qty==D(str(order['executedQty'])),
    'fillArithmeticValid':all(D(str(f['price']))*D(str(f['qty']))==D(str(f['quoteQty'])) for f in fills),
    'sameOrderIdentity':all(str(f['orderId'])==str(order.get('orderId')) for f in fills),
    'economicStatus':'NOT_CERTIFIED_PARENT_QUOTE_MISMATCH'}
  results.append(result)
 except Exception as ex:
  results.append({'orderId':oid,'errorClass':type(ex).__name__,'economicStatus':'UNRESOLVED'})
  if type(ex).__name__=='BudgetDeferred':break
report={'checkedAt':datetime.now(timezone.utc).isoformat(),'scope':'FIVE_PARTIAL_CANCELED_ORDERS',
 'ordersChecked':len(results),'orderQuoteMatchesQtyTimesAvg':sum(x.get('cumQuoteEqualsAvgTimesQty') is True for x in results),
 'exchangeWrites':0,'fullEconomicCertification':False,
 'results':results}
p=R/'weex_trade_1000_five_cumquote_diagnostic.json';temp=p.with_suffix('.tmp')
temp.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(temp,p)
print(json.dumps(report,ensure_ascii=False))
