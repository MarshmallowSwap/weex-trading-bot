"""Transparent WEEX parent-vs-fill monetary tolerance audit (read-only).
Never rewrites historical economics, never grants release.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'weex_1000_parent_quote_mismatch_full_audit.json').read_text())['details']
economy=json.loads((ROOT/'weex_1000_fill_economics_consolidated.json').read_text())
limit_abs=D('.01')
limit_relative=D('.0001') # 0.01 percent
accepted=[];rejected=[];partial=[]
for item in rows:
 if item['status']!='FILLED':
  partial.append(item['orderId']);continue
 quote=D(item['fillQuote']);difference=D(str(item['quotedDifference']))
 amount=abs(difference)
 # Require BOTH monetary and relative caps, not either one.
 allowed=amount<=limit_abs and (quote>0 and amount<=quote*limit_relative)
 row={'orderId':item['orderId'],'symbol':item['symbol'],
      'fillQuoteUSDT':str(quote),'differenceUSDT':str(difference),
      'relativePercent':str((amount/quote*100) if quote>0 else 0)}
 (accepted if allowed else rejected).append(row)
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'scope':'BOUND_1000_WEEX_FILLS_NOT_FULL_ACCOUNT_HISTORY',
 'rule':'BOTH absolute discrepancy <=0.01 USDT and relative discrepancy <=0.01%',
 'absoluteToleranceUSDT':str(limit_abs),'relativeTolerancePercent':'0.01',
 'completeFilledOrders':len(accepted)+len(rejected),
 'ordersWithinTolerance':len(accepted),'ordersOutsideTolerance':len(rejected),
 'partialCanceledOrdersExcludedFromThisTolerance':len(partial),
 'partialCanceledOrderIds':partial,
 'totalAbsoluteFilledDiscrepancyUSDT':str(sum((abs(D(str(x['quotedDifference']))) for x in rows
        if x['status']=='FILLED'),D(0))),
 'maximumAbsoluteFilledDiscrepancyUSDT':str(max((abs(D(str(x['quotedDifference']))) for x in rows
        if x['status']=='FILLED'),default=D(0))),
 'all1000FillIdentitiesVerified':economy.get('fillsLinkedToOrders')==1000,
 'allFillBasedNotionalsAndFeesReconciled':economy.get('allOrdersFillBasedNotionalAndFeesReconciled') is True,
 'acceptedOrders':accepted,'rejectedOrders':rejected,
 'parentFieldWithinStrictToleranceForAll':not rejected and not partial,
 'fullFundingAndBalanceHistoryVerified':False,
 'fullHistoryCertified':False,'productionAccountingGatePassed':False,
 'noGateOrExecutionSettingModified':True,'exchangeWrites':0}
path=ROOT/'weex_parent_quote_strict_tolerance_audit_20261109.json'
tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));os.replace(tmp,path)
print(json.dumps({k:v for k,v in report.items() if k not in ('acceptedOrders','rejectedOrders','partialCanceledOrderIds')}))
