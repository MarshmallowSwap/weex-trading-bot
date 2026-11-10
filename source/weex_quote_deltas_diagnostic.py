"""Explain exchange order quote deltas without treating them as certified fills."""
import json
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
def investigate(r):
    try:
        v=r['verdict'];q=D(str(r['qty']));avg=D(str(r['avgPrice']))
        quote=D(str(r['cumQuote']));summed=sum((D(x['quoteQty']) for x in r['fills']),D(0))
        products=sum((D(x['product']) for x in r['fills']),D(0))
        direct=(quote==summed)
        alternate=(quote==q*avg)
        fill_products_rounded=(abs(products-summed)<=D('0.00000001'))
        return {'symbol':r['symbol'],'observedState':r['status'],
                'fillQuoteUSDT':str(summed),'orderCumQuoteUSDT':str(quote),
                'quoteDeltaUSDT':str(quote-summed),
                'orderQtyTimesReportedAvg':str(q*avg),
                'directQuoteMatch':direct,'orderAvgMultiplicationMatch':alternate,
                'fillPriceTimesQtyCorroborated':fill_products_rounded,
                'classification':('DIRECT_QUOTE_MATCH' if direct else
                   'ORDER_AVG_QUOTE_ALTERNATE_REPRESENTATION_NOT_ECONOMIC_CERTIFICATION'
                   if alternate and fill_products_rounded else 'UNRESOLVED'),
                'economicCertification':False}
    except (KeyError,TypeError,ValueError,InvalidOperation):
        return {'symbol':r.get('symbol'),'classification':'INSUFFICIENT_DATA',
                'economicCertification':False}
def run():
    source=json.loads((ROOT/'weex_economic_forensics_latest.json').read_text(encoding='utf-8'))
    rows=[investigate(x) for x in source['results']]
    out={'checkedAt':datetime.now(timezone.utc).isoformat(),
         'sourceAt':source['at'],'checks':rows,'fullHistoricalCoverage':False,
         'economicCertification':False,'releaseGateOverride':False,'exchangeWrites':False}
    (ROOT/'weex_quote_deltas_diagnostic_latest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    return out
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
