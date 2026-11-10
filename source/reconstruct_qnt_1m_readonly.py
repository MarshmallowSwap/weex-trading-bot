"""WEEX QNT 2026-11-04 historical 1m reconstruction, GET only."""
import json,csv,time,urllib.request,urllib.parse
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from weex_lifecycle import Lifecycle
# Historical endpoint is GET-only; bounded to two documented weight-5 requests.

root=Path(__file__).resolve().parent
tid='wxentry_7f327b721a398e3e86033c73'
e=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
item=e.get(tid)
owned=item['owned']
entry_ms=1793783842260
exit_ms=1793786852705
start=1793782800000
end=min(int(time.time()*1000)-60000,start+99*60000)
def candles(price_type):
    args={'symbol':'QNTUSDT','interval':'1m','startTime':start,
          'endTime':end,'limit':100,'priceType':price_type}
    url='https://api-contract.weex.com/capi/v3/market/historyKlines?'+urllib.parse.urlencode(args)
    req=urllib.request.Request(url,headers={'User-Agent':'WEEX-QNT-Reconstruction-ReadOnly/1'})
    with urllib.request.urlopen(req,timeout=14) as response:data=json.load(response)
    if not isinstance(data,list):raise ValueError('HISTORY_SCHEMA')
    rows=sorted(data,key=lambda x:int(x[0]))
    rows=[r for r in rows if start<=int(r[0])<=end and int(r[6])<=int(time.time()*1000)]
    if len(rows)<60 or len(set(int(r[0]) for r in rows))!=len(rows):raise ValueError('HISTORY_INCOMPLETE')
    if any(int(b[0])-int(a[0])!=60000 for a,b in zip(rows,rows[1:])):raise ValueError('HISTORY_GAPS')
    return rows
last=candles('LAST');mark=candles('MARK')
by_mark={int(r[0]):r for r in mark}
rows=[{'ms':int(r[0]),'open':float(r[1]),'high':float(r[2]),
       'low':float(r[3]),'close':float(r[4]),
       'mark_high':float(by_mark[int(r[0])][2]),
       'mark_low':float(by_mark[int(r[0])][3]),
       'mark_close':float(by_mark[int(r[0])][4])}
      for r in last if int(r[0]) in by_mark]
quantity=D(owned['quantity'])
entry_cost=D(owned['actualEntryCostUSDT'])
entry_fees=D(owned['actualEntryFeesUSDT'])
actual_net=D('1.60702080')
fee_rate=D('0.0008')
target_net=D(item['plan']['targetNetProfitUSDT'])
target_price=(entry_cost+entry_fees+target_net)/(quantity*(1-fee_rate))
def pnl(price,qty=quantity):
    gross=qty*D(str(price))
    return gross-entry_cost*(qty/quantity)-entry_fees*(qty/quantity)-gross*fee_rate
def atr(data,i,length=14):
    if i<length:return None
    trs=[max(data[k]['high']-data[k]['low'],
             abs(data[k]['high']-data[k-1]['close']),
             abs(data[k]['low']-data[k-1]['close'])) for k in range(i-length+1,i+1)]
    return sum(trs)/length
def run_trailing(multiplier, activation):
    # Signal activation at a COMPLETED candle's mark close, so trading begins on following candle.
    active=False;peak=None;stop=None
    for i,r in enumerate(rows):
        if r['ms']<entry_ms//60000*60000:continue
        if not active:
            if i>=14 and r['mark_close']>=activation:
                active=True;peak=r['close']
                a=atr(rows,i)
                if a is None:return {'state':'insufficient_history'}
                stop=peak-multiplier*a
                activation_ms=r['ms']
            continue
        if r['low']<=stop:
            return {'state':'EXIT','timeUTC':datetime.fromtimestamp(r['ms']/1000,timezone.utc).isoformat(),
                    'exitPriceModel':round(stop,4),'netModelUSDT':round(float(pnl(stop)),4),
                    'activationUTC':datetime.fromtimestamp(activation_ms/1000,timezone.utc).isoformat(),
                    'atrMultiplier':multiplier,'triggerModel':'MARK_1M_CLOSE'}
        peak=max(peak,r['high'])
        a=atr(rows,i)
        stop=max(stop,peak-multiplier*a)
    return {'state':'OPEN_AT_DATA_END','lastClose':rows[-1]['close'],
            'markToMarketNetUSDT':round(float(pnl(rows[-1]['close'])),4),
            'highestObservedPrice':max(r['high'] for r in rows),'atrMultiplier':multiplier}
sim=[run_trailing(m,float(target_price)) for m in (1,1.5,2)]
actual_exit=next((r for r in rows if r['ms']<=exit_ms<r['ms']+60000),None)
entry_candle=next((r for r in rows if r['ms']<=entry_ms<r['ms']+60000),None)
mark_trigger=[r for r in rows if r['ms']>=entry_ms//60000*60000 and r['ms']<=exit_ms and r['mark_high']>=float(owned['tpRequest']['triggerPrice'])]
high_after=max((r['high'] for r in rows if r['ms']>=exit_ms//60000*60000),default=None)
summary={'symbol':'QNTUSDT','direction':'LONG','fromUTC':datetime.fromtimestamp(start/1000,timezone.utc).isoformat(),
         'throughUTC':datetime.fromtimestamp(rows[-1]['ms']/1000,timezone.utc).isoformat(),
         'candlesLAST':len(last),'candlesMARK':len(mark),'alignedCandles':len(rows),
         'entryUTC':datetime.fromtimestamp(entry_ms/1000,timezone.utc).isoformat(),
         'exitUTC':datetime.fromtimestamp(exit_ms/1000,timezone.utc).isoformat(),
         'entryVWAP':str(entry_cost/quantity),'quantity':str(quantity),
         'targetNetUSDT':str(target_net),'targetPriceCalculated':str(target_price),
         'weexTrigger':owned['tpRequest']['triggerPrice'],
         'actualNetUSDT':str(actual_net),'entryCandle':entry_candle,'exitCandle':actual_exit,
         'markTriggerCandlesBeforeExit':len(mark_trigger),'firstMarkTrigger':mark_trigger[0] if mark_trigger else None,
         'maximumLastAfterExit':high_after,
         'modelNetAtMaximumAfterExitUSDT':str(pnl(high_after)) if high_after is not None else None,
         'dataIntegrity':{'entryVWAPOutsideEntryCandle':not(entry_candle['low']<=float(entry_cost/quantity)<=entry_candle['high']),
                          'exitVWAPOutsideExitCandle':not(actual_exit['low']<=195.63430188679245<=actual_exit['high']),
                          'status':'CANDLE_FILL_MISMATCH_REQUIRES_EXCHANGE_RECONCILIATION',
                          'backtestGrade':'EXPLORATORY_ONLY'},
         'trailingModels':sim,
         'limits':['1m OHLC does not identify intrabar order of high/low',
                   'trailing simulated stop fill at threshold with no slippage',
                   'Mark close activation is not exchange-native intrabar trigger',
                   'Funding excluded','Results are single-trade exploratory, not strategy validation']}
out=root/'qnt_20261104_reconstruction'
out.mkdir(exist_ok=True)
with (out/'weex_1m_last_mark.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
(out/'comparison.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
