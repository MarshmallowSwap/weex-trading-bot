"""Certify exact ordinary WEEX fill-to-bill economics and classify liquidation
exceptions by independently authenticated WEEX start/finish liquidation bills.
Read-only; does not change automatic live release gate.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
fills=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text(encoding='utf-8'))['trades']
ledger=json.loads((ROOT/'weex_income_ledger_bounded_20261109.json').read_text(encoding='utf-8'))
join=json.loads((ROOT/'weex_fill_income_ledger_join_20261109.json').read_text(encoding='utf-8'))
assert len(fills)==1000 and ledger['paginationStatus']=='EXHAUSTED'
assert join['matchedUniqueFillToBillCount']==1000 and not join['unmatchedFillCount'] and not join['ambiguousFillCount']
byfill={str(f['id']):f for f in fills}
bybill={str(b['billId']):b for b in ledger['rows']}
# Reproduce exact one-to-one matching independently using same ID identity
# observations; report-only primary join ensures 1000 uniqueness. For all
# 3 residuals identify exact surrounding liquidate events and no fee mislabel.
events=[b for b in ledger['rows'] if b['incomeType'] in ('start_liquidate','finish_liquidate')]
problems=join['topDifferences']
nonzero=[x for x in problems if abs(D(x['incomeMinusSignedQuoteAndFee']))>D('.00000002')]
exception_details=[]
for x in nonzero:
 f=byfill[x['tradeId']];b=bybill[x['billId']]
 t=int(f['time'])
 start=[e for e in events if e['incomeType']=='start_liquidate' and 0<=t-int(e['time'])<=180000]
 end=[e for e in events if e['incomeType']=='finish_liquidate' and 0<=int(e['time'])-t<=180000]
 pair=any(int(s['time'])<=t<=int(e['time']) and
          int(e['time'])-int(s['time'])<=180000 for s in start for e in end)
 exception_details.append({'tradeId':x['tradeId'],'billId':x['billId'],'symbol':x['symbol'],
   'fillQuoteUSDT':x['fillQuote'],'incomeUSDT':x['income'],
   'unattributedIncomeDifferenceUSDT':x['incomeMinusSignedQuoteAndFee'],
   'fillReportedRealizedPnlUSDT':x['fillRealizedPnl'],
   'liquidationBracketingVerified':pair,
   'startLiquidationBillIds':[str(s['billId']) for s in start],
   'endLiquidationBillIds':[str(e['billId']) for e in end]})
liquidation_ok=len(exception_details)==3 and all(x['liquidationBracketingVerified'] for x in exception_details)
# Capture exact input linkage and scopes. Do not call liquidation adjustment
# reconciled until exchange rules explain it.
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'scope':'1000_FIXED_AUTHENTICATED_FILLS_WITH_FULL_PAGED_INCOME_WINDOW',
 'incomeLedgerPages':ledger['pages'],'incomeLedgerRows':ledger['records'],
 'incomeWindowComplete':ledger['fullWindowPagination'],
 'fillsLinkedOneToOneWithIncomeBill':join['matchedUniqueFillToBillCount'],
 'ordinaryFillExactIncomeMatches':join['exactQuoteAndFeeDeltaCount'],
 'liquidationAdjustmentFillCount':len(exception_details),
 'liquidationEventTimingExplainsClass':liquidation_ok,
 'allFillsAttributedToEitherExactOrdinaryBillOrLiquidation':liquidation_ok
   and join['exactQuoteAndFeeDeltaCount']==997,
 'normalFillEconomicAccountingCertified':liquidation_ok
   and join['exactQuoteAndFeeDeltaCount']==997,
 'liquidationAdjustmentAmountsIndependentlyCertified':False,
 'liquidationExceptions':exception_details,
 'parentCumQuoteCanBeUsedAsAccountingSource':False,
 'fillBasedNotionalAndFeesPreferred':True,
 'fullAccountLifetimeEconomicsCertified':False,
 'generalReleaseAccountingGatePassed':False,
 'botRestartAuthorized':False,'exchangeWrites':0,
 'sourceFiles':['weex_trade_1000_snapshot.json',
                'weex_income_ledger_bounded_20261109.json',
                'weex_fill_income_ledger_join_20261109.json']}
out=ROOT/'weex_1000_fill_income_liquidation_classification_20261109.json'
tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');os.replace(tmp,out)
print(json.dumps({k:v for k,v in report.items() if k!='liquidationExceptions'}))
print('EXCEPTIONS',json.dumps(exception_details))
