"""Read-only LTC closure diagnostic from WEEX futures account/history."""
import json,time
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from weex_live_worker import Reader
from weex_lifecycle import Lifecycle
from weex_execution_readonly import pages
from weex_api_budget import recovery
root=Path(__file__).resolve().parent
tid='wxentry_1566be92f4fe10fdd0b83ca3'
engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
item=engine.get(tid);r=Reader(root)
symbol=item['symbol'];end=int(time.time()*1000)
with recovery():
    positions,regular,algos=r.account()
    orders=pages(r.read,'get_capi_v3_order_history',identity='orderId',start=0,
                 symbol=symbol,startTime=item['created']-1000,endTime=end)
    tps=r.read('get_capi_v3_allAlgoOrders',symbol=symbol,startTime=item['created']-1000,endTime=end,limit=1000)
byid={str(o['orderId']):o for o in orders}
def add_order(oid):
    try:
        with recovery():o=r.read('get_capi_v3_order',orderId=oid)
        if o.get('symbol')==symbol and o.get('orderId'):byid[str(o['orderId'])]=o
    except Exception as exc:print('DIRECT_ORDER_ERROR',type(exc).__name__)
add_order(item['owned']['entryOrderId'])
for a in tps.get('orders',[]) if isinstance(tps,dict) else []:
    if a.get('algoStatus') in ('FILLED','TRIGGERED'):
        oid=a.get('actualOrderId') or a.get('algoId')
        if oid:add_order(oid)
fills={}
for o in byid.values():
    if D(str(o.get('executedQty') or 0))>0:
        try:
            with recovery():f=r.read('get_capi_v3_userTrades',symbol=symbol,orderId=o['orderId'],limit=100)
            if isinstance(f,list):
                qty=sum((D(str(x['qty'])) for x in f),D(0))
                value=sum((D(str(x['qty']))*D(str(x['price'])) for x in f),D(0))
                fees=sum((D(str(x['commission'])) for x in f),D(0))
                fills[str(o['orderId'])]={'count':len(f),'qty':str(qty),'value':str(value),
                                          'fees':str(fees),'vwap':str(value/qty) if qty else None,
                                          'firstMs':min((int(x['time']) for x in f),default=None),
                                          'lastMs':max((int(x['time']) for x in f),default=None)}
        except Exception as exc:fills[str(o['orderId'])]={'error':type(exc).__name__}
data={'tradeId':tid,'state':item['state'],'positionOpen':any(p.get('symbol')==symbol for p in positions),
      'targetNetUSDT':item['plan'].get('targetNetProfitUSDT'),
      'targetTrigger':item['owned']['tpRequest'].get('triggerPrice'),
      'entryCostUSDT':item['owned'].get('actualEntryCostUSDT'),
      'entryFeesUSDT':item['owned'].get('actualEntryFeesUSDT'),
      'ownedQuantity':item['owned'].get('quantity'),
      'algoHistoryComplete':tps.get('hasMore') is False if isinstance(tps,dict) else False,
      'algos':[{'algoId':str(a.get('algoId')),'clientAlgoId':a.get('clientAlgoId'),
                'status':a.get('algoStatus'),'trigger':a.get('triggerPrice'),'actualOrderId':a.get('actualOrderId'),
                'reduceOnly':a.get('reduceOnly'),'quantity':a.get('quantity')}
                for a in tps.get('orders',[]) if a.get('symbol')==symbol],
      'orders':[{'orderId':str(o.get('orderId')),'status':o.get('status'),'type':o.get('type'),
                 'side':o.get('side'),'reduceOnly':o.get('reduceOnly'),
                 'executedQty':o.get('executedQty'),'avgPrice':o.get('avgPrice'),
                 'cumQuote':o.get('cumQuote'),'time':o.get('time')}
                for o in sorted(byid.values(),key=lambda x:int(x.get('time') or 0))],
      'fills':fills}
dest=root/'ltc_closure_diagnostic.json'
dest.write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps(data,indent=2))
