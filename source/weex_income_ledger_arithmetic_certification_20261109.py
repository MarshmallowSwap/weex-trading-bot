"""Bounded WEEX account ledger audit, independent arithmetic proof.

Verifies the exact authenticated ledger balance chain and links the 1000-fill
snapshot. Does not certify full account history, liquidation fee semantics,
or production crash during an exchange POST.
"""
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
import json,os
ROOT=Path(__file__).resolve().parent
def reconcile(records):
 if not isinstance(records,list) or len(records)<2:
  return {'verified':False,'reason':'INSUFFICIENT_BILLS'}
 try:
  ids=[str(r['billId']) for r in records]
  if len(ids)!=len(set(ids)):return {'verified':False,'reason':'DUPLICATE_BILL_IDS'}
  ordered=sorted(records,key=lambda x:(int(x['time']),int(x['billId'])))
  gap=[]
  for a,b in zip(ordered,ordered[1:]):
   delta=D(str(b['balance']))-D(str(a['balance']))
   income=D(str(b['income']))
   if not all(x.is_finite() for x in (delta,income)) or delta!=income:
    gap.append({'billId':str(b['billId']),'balanceDelta':str(delta),'income':str(income)})
  movements=sum((D(str(x['income'])) for x in ordered[1:]),D(0))
  end_minus_start=D(str(ordered[-1]['balance']))-D(str(ordered[0]['balance']))
  return {'verified':not gap and movements==end_minus_start,
    'billCount':len(ordered),'transitionsChecked':len(ordered)-1,
    'gaps':gap,'firstBillId':str(ordered[0]['billId']),
    'lastBillId':str(ordered[-1]['billId']),
    'firstBalanceUSDT':str(ordered[0]['balance']),
    'lastBalanceUSDT':str(ordered[-1]['balance']),
    'sumMovementUSDT':str(movements),
    'firstToLastBalanceDeltaUSDT':str(end_minus_start)}
 except (KeyError,TypeError,ValueError,InvalidOperation,ArithmeticError):
  return {'verified':False,'reason':'INVALID_BILL_DATA'}
def run():
 ledger=json.loads((ROOT/'weex_income_ledger_bounded_20261109.json').read_text())
 join=json.loads((ROOT/'weex_fill_income_ledger_join_20261109.json').read_text())
 classes=json.loads((ROOT/'weex_1000_fill_income_liquidation_classification_20261109.json').read_text())
 trial=json.loads((ROOT/'weex_cross_one_shot_real_independent_audit_20261109.json').read_text())
 assert ledger['source']=='AUTHENTICATED_WEEX_FUTURES_ACCOUNT_INCOME'
 result=reconcile(ledger['rows'])
 bounded_ok=(result['verified'] and ledger.get('paginationStatus')=='EXHAUSTED'
    and ledger.get('fullWindowPagination') is True and ledger.get('pages')==14
    and ledger.get('records')==len(ledger['rows'])==1335
    and join['matchedUniqueFillToBillCount']==1000
    and join['unmatchedFillCount']==0 and join['ambiguousFillCount']==0
    and classes['normalFillEconomicAccountingCertified'] is True
    and classes['liquidationEventTimingExplainsClass'] is True
    and classes['liquidationAdjustmentFillCount']==3
    and trial['allIndependentChecksPassed'] is True)
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
   'scope':'WEEX_ACCOUNT_USDT_LEDGER_IN_EXHAUSTED_BOUNDED_WINDOW',
   'windowStartMs':ledger['startMs'],'windowEndMs':ledger['endMs'],
   'ledgerWindowComplete':ledger['fullWindowPagination'],
   'balanceArithmetic':result,
   'all1000FillsLinkedToBills':join['all1000DirectBillsMatched'],
   '997OrdinaryFillsQuoteAndFeeMatch':classes['ordinaryFillExactIncomeMatches']==997,
   '3LiquidationsPresentInAuthoritativeBillLedger':classes['liquidationEventTimingExplainsClass'],
   'liquidationFeeLabelsIndependentlyCertified':False,
   'boundedLedgerAccountingCertified':bounded_ok,
   'entireAccountLifetimeCertified':False,
   'realOrderDuringCrashCertified':False,
   'generalProductionReleaseAuthorized':False,
   'productionGateChanged':False,'newExchangeWrites':0}
 output=ROOT/'weex_income_ledger_arithmetic_certification_20261109.json'
 temp=output.with_suffix('.tmp')
 temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');os.replace(temp,output)
 print(json.dumps(report))
if __name__=='__main__':run()
