"""Explain parent cumQuote mismatches on every 1000-trade snapshot order.

The snapshot was independently collected via authenticated WEEX GET. The
checkpoint totals are verified against it. No exchange calls or write mode.
"""
import json,os
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
fills=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text())['trades']
audits=json.loads((ROOT/'weex_trade_1000_economics_checkpoint.json').read_text())['orders']
group=defaultdict(list)
for f in fills:group[str(f['orderId'])].append(f)
assert len(group)==137 and set(group)==set(audits)
summary=Counter()
data=[]
for oid,f in group.items():
 a=audits[oid]
 q=sum((D(str(x['qty'])) for x in f),D(0))
 v=sum((D(str(x['quoteQty'])) for x in f),D(0))
 prices={D(str(x['price'])) for x in f}
 delta=a.get('parentQuoteDifferenceUSDT')
 mismatch=delta is not None and D(str(delta))!=0
 if a['verified']:
  assert q==D(str(a['quantity'])) if a.get('quantity') else q>0
  assert D(str(a['notionalUSDT']))==v
  assert mismatch==(a.get('cumQuoteEqualFill') is False)
 status='FILLED' if a['verified'] else 'PARTIAL_CANCELED'
 summary[(status,'parent_mismatch' if mismatch else 'parent_equal')]+=1
 data.append({'orderId':oid,'symbol':f[0]['symbol'],'status':status,
   'fillCount':len(f),'distinctFillPrices':len(prices),
   'parentQuoteMismatch':mismatch,
   'fillQuote':str(v),'quotedDifference':delta,
   'exchangeDocumentedParentSemanticsUnresolved':mismatch})
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'scope':'BOUND_1000_TRADE_SNAPSHOT',
 'verifiedFilledOrders':sum(x['verified'] for x in audits.values()),
 'filledWithParentQuoteMismatch':summary[('FILLED','parent_mismatch')],
 'filledWithParentQuoteEqual':summary[('FILLED','parent_equal')],
 'filledMismatchMultiplePrices':sum(x['status']=='FILLED' and x['parentQuoteMismatch'] and x['distinctFillPrices']>1 for x in data),
 'filledMismatchSinglePrice':sum(x['status']=='FILLED' and x['parentQuoteMismatch'] and x['distinctFillPrices']==1 for x in data),
 'uncertifiedPartialCanceled':sum(not x['verified'] for x in audits.values()),
 'parentFieldsNotAuthoritative':True,
 'fullHistoryVerified':False,'liveReleaseGo':False,'exchangeWrites':0,'details':data}
p=ROOT/'weex_1000_parent_quote_mismatch_full_audit.json'
t=p.with_suffix('.tmp');t.write_text(json.dumps(report,indent=2));os.replace(t,p)
print(json.dumps({k:v for k,v in report.items() if k!='details'}))
