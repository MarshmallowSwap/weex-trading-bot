"""Read-only offline WEEX field contradiction audit, five partial orders.

Official API docs describe avgPrice as average fill price and cumQuote as
cumulative quote. Flag disagreement with independently sourced fill ledger.
This is not a patch to exchange data or release gate.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
source=json.loads((R/'weex_trade_1000_five_cumquote_diagnostic.json').read_text())
rows=source['results']
if len(rows)!=5 or len({x['orderId'] for x in rows})!=5:raise ValueError('FIVE_EXACT_ORDERS_REQUIRED')
out=[]
for r in rows:
    qty=D(r['fillQtySum']);q=D(r['fillQuoteSum']);reported=D(r['cumQuote'])
    avg=D(r['avgPrice']);weighted=q/qty
    if not qty or r['status']!='CANCELED' or not r['qtyMatches'] or not r['fillArithmeticValid'] or not r['sameOrderIdentity']:
        raise ValueError('BAD_ORDER_OR_FILL_EVIDENCE')
    discrepancy=reported-q
    matches_parent=reported==avg*qty
    inconsistent=matches_parent and (reported!=q) and avg!=weighted
    out.append({'orderId':r['orderId'],'symbol':r['symbol'],
      'fillCount':r['numberOfDistinctFillPrices'],'executedQty':str(qty),
      'fillQuoteUSDT':str(q),'parentQuoteUSDT':str(reported),
      'quoteDifferenceUSDT':str(discrepancy),
      'weightedFillPrice':str(weighted),'parentAvgPrice':str(avg),
      'parentQuoteEqualsParentAvgTimesQty':matches_parent,
      'contradictsDocumentedAverageAndCumulativeQuote':inconsistent,
      'classification':'PARENT_FIELDS_CONTRADICT_EXECUTION_LEDGER' if inconsistent else 'REVIEW_REQUIRED'})
summary={'checkedAt':datetime.now(timezone.utc).isoformat(),'scope':'FIVE_CANCELED_PARTIALLY_FILLED_UAIUSDT',
   'documentedAvgPriceDefinition':'average fill price',
   'documentedCumQuoteDefinition':'cumulative filled quote amount',
   'ordersExamined':len(out),'fieldContradictions':sum(x['contradictsDocumentedAverageAndCumulativeQuote'] for x in out),
   'sumFillNotionalUSDT':str(sum((D(x['fillQuoteUSDT']) for x in out),D(0))),
   'sumParentCumQuoteUSDT':str(sum((D(x['parentQuoteUSDT']) for x in out),D(0))),
   'sumParentMinusFillQuoteUSDT':str(sum((D(x['quoteDifferenceUSDT']) for x in out),D(0))),
   'suggestedAccountingValue':'FILL_QUOTE_SUM_NOT_PARENT_CUMQUOTE',
   'fullEconomicCertification':False,'fullHistoricalCoverage':False,
   'productionReleaseAllowed':False,'exchangeWrites':0,'details':out}
path=R/'weex_trade_1000_parent_field_contradictions.json'
tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(summary,indent=2),encoding='utf-8');os.replace(tmp,path)
print(json.dumps({k:v for k,v in summary.items() if k!='details'}))
