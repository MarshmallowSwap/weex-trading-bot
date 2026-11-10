"""Independent WEEX 1000 fills versus complete bounded income-ledger window.
Match one-to-one by symbol, direction, timestamp and commission. Never claim
full account-history PnL coverage beyond the observed window.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
fills=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text(encoding='utf-8'))['trades']
ledger=json.loads((ROOT/'weex_income_ledger_bounded_20261109.json').read_text(encoding='utf-8'))
assert len(fills)==1000 and ledger['fullWindowPagination'] is True
bills=[b for b in ledger['rows'] if str(b.get('incomeType','')).startswith('position_') and b.get('incomeType')!='position_funding']
assert len({str(b['billId']) for b in bills})==len(bills)
by_symbol=defaultdict(list)
for i,b in enumerate(bills):by_symbol[b['symbol']].append((i,b))
used=set();matched=[];unmatched=[];ambiguous=[]
for f in fills:
 side=f['side'];pos=f['positionSide']
 expected=('position_open_' if (side=='BUY' and pos=='LONG') or (side=='SELL' and pos=='SHORT') else 'position_close_')+pos.lower()
 fee=D(str(f['commission']));time=int(f['time'])
 candidates=[]
 for i,b in by_symbol.get(f['symbol'],[]):
  if i in used or b['incomeType']!=expected:continue
  lag=abs(int(b['time'])-time)
  bill_fee=D(str(b.get('fillFee','0')))
  if lag<=15000 and abs(bill_fee-fee)<=D('.00000002'):
   candidates.append((lag,abs(bill_fee-fee),i,b))
 candidates.sort(key=lambda x:(x[0],x[1]))
 if not candidates:
  unmatched.append({'tradeId':str(f['id']),'symbol':f['symbol'],'time':time,
    'commission':str(fee),'expectedType':expected});continue
 if len(candidates)>1 and candidates[0][:2]==candidates[1][:2]:
  ambiguous.append({'tradeId':str(f['id']),'count':len(candidates)});continue
 lag,fee_diff,i,b=candidates[0]
 used.add(i)
 fq=D(str(f['quoteQty']));pnl=D(str(f.get('realizedPnl','0')))
 income=D(str(b['income']));signed=(-fq if expected=='position_open_long' else fq if expected=='position_close_long'
     else fq if expected=='position_open_short' else -fq)
 # For LONG/SHORT, income may also reflect PnL separately. Record actual difference.
 predicted=signed-fee
 delta=income-predicted
 matched.append({'tradeId':str(f['id']),'billId':str(b['billId']),
   'symbol':f['symbol'],'lagMs':lag,'fillQuote':str(fq),
   'income':str(income),'incomeMinusSignedQuoteAndFee':str(delta),
   'fillRealizedPnl':str(pnl),'feeUSDT':str(fee),'incomeType':expected})
exact=[x for x in matched if abs(D(x['incomeMinusSignedQuoteAndFee']))<=D('.00000002')]
deltas=sorted(matched,key=lambda x:abs(D(x['incomeMinusSignedQuoteAndFee'])),reverse=True)
out={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'ledgerScope':'EXHAUSTED_2026_10_26_TO_2026_11_09_WINDOW',
 'snapshotFills':len(fills),'ledgerRecords':len(ledger['rows']),
 'positionBills':len(bills),'matchedUniqueFillToBillCount':len(matched),
 'exactQuoteAndFeeDeltaCount':len(exact),
 'unmatchedFillCount':len(unmatched),'ambiguousFillCount':len(ambiguous),
 'maxAbsoluteIncomeQuoteDifferenceUSDT':str(max((abs(D(x['incomeMinusSignedQuoteAndFee'])) for x in matched),default=D(0))),
 'differencePatterns':dict(Counter(x['incomeType'] for x in deltas[:30])),
 'topDifferences':deltas[:20],'unmatched':unmatched[:150],
 'all1000DirectBillsMatched':len(matched)==1000 and not unmatched and not ambiguous,
 'fullAccountHistoryCertified':False,'economicLedgerDirectMatchCertified':False,
 'exchangeWrites':0,'releaseGateChanged':False}
p=ROOT/'weex_fill_income_ledger_join_20261109.json';tmp=p.with_suffix('.tmp')
tmp.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');os.replace(tmp,p)
print(json.dumps({k:v for k,v in out.items() if k not in ('topDifferences','unmatched')}))
print('TOP_EXAMPLES',json.dumps(deltas[:5]))
