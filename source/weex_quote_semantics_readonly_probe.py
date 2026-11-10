"""Read-only probe for WEEX cumQuote alternate encoding on exact five TP orders."""
from weex_live_worker import Reader,ROOT
from decimal import Decimal as D
from pathlib import Path
import json
def check(order,fills):
 if not isinstance(order,dict) or not isinstance(fills,list) or not 0<len(fills)<100: return {'state':'INCOMPLETE'}
 if any(not f.get('id') for f in fills) or len({str(f.get('id')) for f in fills})!=len(fills):return {'state':'DUPLICATE_FILLS'}
 if order.get('status')!='FILLED':return {'state':'ORDER_NOT_FINAL'}
 if any(str(f.get('orderId'))!=str(order.get('orderId')) or f.get('symbol')!=order.get('symbol') or f.get('side')!=order.get('side') or f.get('positionSide')!=order.get('positionSide') for f in fills):return {'state':'IDENTITY_MISMATCH'}
 qty=sum((D(str(f['qty'])) for f in fills),D(0))
 val=sum((D(str(f['quoteQty'])) for f in fills),D(0))
 fee=sum((D(str(f['commission'])) for f in fills),D(0))
 if any(D(str(f['qty']))*D(str(f['price']))!=D(str(f['quoteQty'])) or f.get('commissionAsset')!='USDT' for f in fills):return {'state':'FILL_ECONOMICS_INVALID'}
 if qty!=D(str(order['executedQty'])):return {'state':'QUANTITY_MISMATCH'}
 avg=D(str(order['avgPrice']));reported=D(str(order['cumQuote']))
 alternative=qty*avg
 multi=len({D(str(f['price'])) for f in fills})>1
 return {'state':('WEEX_LAST_PRICE_TIMES_QTY_CORROBORATED' if reported!=val and reported==alternative and multi and avg in {D(str(f['price'])) for f in fills} else 'DIRECT_QUOTE_MATCH' if reported==val else 'UNEXPLAINED'),
 'fillCount':len(fills),'qty':str(qty),'fillNotional':str(val),'reportedCumQuote':str(reported),
 'alternativeQtyTimesAvgPrice':str(alternative),'avgPriceMatchesOneFill':avg in {D(str(f['price'])) for f in fills},
 'distinctFillPrices':len({D(str(f['price'])) for f in fills}),
 'feeUSDT':str(fee),'orderQuoteDelta':str(reported-val),'isComplete':True}
def run():
 import live_control
 if live_control.state(ROOT)['mode']!='STOPPED':raise ValueError('LIVE_NOT_STOPPED')
 r=Reader(ROOT)
 src=json.loads((ROOT/'live_recent_fill_reconciliation_latest.json').read_text(encoding='utf-8'))
 results=[]
 for x in src['items']:
  order=r.read('get_capi_v3_order',orderId=x['orderId'])
  fills=r.read('get_capi_v3_userTrades',symbol=x['symbol'],orderId=x['orderId'],limit=100)
  results.append({'symbol':x['symbol'],'orderId':x['orderId'],**check(order,fills)})
 return {'results':results,'allAlternativeCorroborated':all(x['state'] in ('WEEX_LAST_PRICE_TIMES_QTY_CORROBORATED','DIRECT_QUOTE_MATCH') for x in results),'exchangeWrites':0}
if __name__=='__main__':print(json.dumps(run()))
