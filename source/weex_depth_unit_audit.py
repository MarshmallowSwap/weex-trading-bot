"""Reproducible dimensional evidence. Correlation is not a unit declaration."""
import json,urllib.request,urllib.parse
from decimal import Decimal
from datetime import datetime,timezone
from pathlib import Path

def get(path,**params):
    url='https://api-contract.weex.com'+path+'?'+urllib.parse.urlencode(params)
    with urllib.request.urlopen(url,timeout=12) as r:return json.load(r)

def assess(symbol,meta,book,ticker,trades):
    if meta.get('symbol')!=symbol or ticker.get('symbol')!=symbol:raise ValueError('SYMBOL_MISMATCH')
    count=0;quote_ok=True
    for trade in trades:
        p,q,v=(Decimal(str(trade[k])) for k in ('price','qty','quoteQty'))
        if not all(x.is_finite() for x in (p,q,v)) or p<=0 or q<=0 or v<0:raise ValueError('INVALID_TRADE')
        quote_ok=quote_ok and abs(p*q-v)<=max(Decimal('0.00000001'),abs(v)*Decimal('0.000001'))
        count+=1
    matches={}
    for side,pkey,qkey in (('bids','bidPrice','bidQty'),('asks','askPrice','askQty')):
        matches[side]=any(Decimal(p)==Decimal(ticker[pkey]) and Decimal(q)==Decimal(ticker[qkey]) for p,q in book[side])
    multiplier=Decimal(str(meta['contractVal']))
    if not multiplier.is_finite() or multiplier<=0:raise ValueError('INVALID_CONTRACT_SIZE')
    scenarios={}
    for side in ('bids','asks'):
        raw=sum((Decimal(p)*Decimal(q) for p,q in book[side]),Decimal(0))
        scenarios[side]={'ifSizeIsBaseAssetUSDT':str(raw),'ifSizeIsContractsUSDT':str(raw*multiplier)}
    return {'symbol':symbol,'contractVal':str(multiplier),'sampledTrades':count,
       'tradeQuoteEqualsPriceTimesBaseQty':bool(count and quote_ok),'bookTickerExactMatches':matches,
       'notionalScenarios':scenarios,'depthUnitVerified':False,
       'conclusion':'CROSS_SOURCE_COMPARISON_ONLY_NO_EXPLICIT_V3_BOOK_UNIT_DECLARATION'}

def run():
    results=[]
    for s in ('BTCUSDT','ETHUSDT','SOLUSDT','1000PEPEUSDT','XPINUSDT'):
        try:
            meta=next(x for x in get('/capi/v3/market/exchangeInfo',symbol=s)['symbols'] if x['symbol']==s)
            book=get('/capi/v3/market/depth',symbol=s,limit=15)
            ticker=next(x for x in get('/capi/v3/market/ticker/bookTicker',symbol=s) if x['symbol']==s)
            trades=get('/capi/v3/market/trades',symbol=s,limit=10)
            results.append(assess(s,meta,book,ticker,trades))
        except Exception as exc:results.append({'symbol':s,'error':type(exc).__name__,'depthUnitVerified':False})
    return {'checkedAt':datetime.now(timezone.utc).isoformat(),'results':results,'ordersSubmitted':False,
      'verified':False,'requiredConfirmation':
      'For GET /capi/v3/market/depth, is each bids/asks size expressed in base-asset units, contract count, or another unit? Does contractVal need to be applied? Please confirm for standard and multiplied symbols such as 1000PEPEUSDT.',
      'source':'https://www.weex.com/api-doc/catalog/core-trading-futures/api/rest-api/market-api'}

if __name__=='__main__':
    report=run()
    path=Path(__file__).with_name('depth_units_live_evidence.json')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'symbols':len(report['results']),'verified':False,'exchangeWrites':False}))
