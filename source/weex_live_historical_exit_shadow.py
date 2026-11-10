"""Read-only bounded WEEX historical EXIT candidate survey for unresolved lifecycles.

Any missing or truncated page blocks automatic resolution. This audit
does NOT assert bot ownership or close lifecycle records; a historical
reduceOnly order requires fill provenance before classification.
"""
import json
from weex_live_worker import Reader,ROOT
from weex_live_unresolved_local_evidence import local_records
from weex_execution_readonly import pages

def run():
    reader=Reader(ROOT)
    result=[]
    for trade in local_records():
        sym=trade['symbol']
        out={'symbol':sym,'tradeId':trade['tradeId'],
             'entryOrderId':trade['entryOrderId'],'autoClear':False,
             'writes':0}
        try:
            history=pages(reader.read,'get_capi_v3_order_history',
                          identity='orderId',start=0,max_pages=5,symbol=sym)
            exits=[x for x in history if x.get('reduceOnly') is True]
            confirmed=[x for x in exits if x.get('status')=='FILLED' and
                       x.get('executedQty') not in (None,'0','0.0')]
            out.update(historyCompleteWithinFivePages=True,
                       historyOrders=len(history),
                       reduces=len(exits),filledReduceOrders=len(confirmed),
                       exitCandidateOrderIds=[str(x.get('orderId')) for x in confirmed[:15]],
                       note='Exit candidates only, not matched to bot positionId')
        except Exception as exc:
            out.update(historyCompleteWithinFivePages=False,
                       errorType=type(exc).__name__)
        result.append(out)
    return {'source':'WEEX_LIVE_READ_ONLY','results':result,
            'canChangeTradeState':False,'liveWrites':0}
if __name__=='__main__':print(json.dumps(run()))
