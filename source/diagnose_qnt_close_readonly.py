"""READ ONLY diagnostic for QNT historical entry and TP execution."""
import json
from decimal import Decimal
from pathlib import Path
from weex_lifecycle import Lifecycle
from weex_live_worker import Reader
from weex_api_budget import recovery

tid='wxentry_7f327b721a398e3e86033c73'
engine=Lifecycle(Path('weex_user_live_lifecycle.sqlite3'),None,lambda:{})
item=engine.get(tid)
owned=item['owned']; proof=owned.get('entryFillEvidence') or {}
r=Reader()
summary={'tradeId':tid,'symbol':item['symbol'],'journalState':item['state'],
         'savedEntryFills':len(proof.get('fills') or []),
         'savedFillDigestPresent':bool(proof.get('fillsDigest'))}
with recovery():
    order=r.read('get_capi_v3_order',orderId=owned['entryOrderId'])
    current_fills=r.read('get_capi_v3_userTrades',symbol=item['symbol'],orderId=owned['entryOrderId'],limit=100)
    tp_history=r.read('get_capi_v3_allAlgoOrders',symbol=item['symbol'],
                      startTime=item['created']-1000,endTime=__import__('time').time_ns()//1000000,limit=1000)
def num(x):
    return str(Decimal(str(x)))
summary['entry']={'orderStatus':order.get('status'),'executedQty':order.get('executedQty'),
    'cumQuote':order.get('cumQuote'),'avgPrice':order.get('avgPrice'),
    'currentFills':len(current_fills) if isinstance(current_fills,list) else 'INVALID',
    'currentFillValue':str(sum((Decimal(str(f['qty']))*Decimal(str(f['price'])) for f in current_fills),Decimal(0))) if isinstance(current_fills,list) else None,
    'savedFillValue':str(sum((Decimal(str(f['qty']))*Decimal(str(f['price'])) for f in proof.get('fills',[])),Decimal(0)))}
algos=tp_history.get('orders') if isinstance(tp_history,dict) else None
summary['tpHistoryComplete']=tp_history.get('hasMore') is False if isinstance(tp_history,dict) else False
summary['tpHistory']=[{'algoId':str(a.get('algoId')),'algoStatus':a.get('algoStatus'),
                       'actualOrderId':str(a.get('actualOrderId')),'clientAlgoId':a.get('clientAlgoId')}
                      for a in (algos or []) if str(a.get('algoId'))==str(engine.writes(tid)['TP']['response'][0]['orderId'])]
print(json.dumps(summary,indent=2))
