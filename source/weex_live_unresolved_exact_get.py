"""Exact authenticated GET verification of historical WEEX bot entry IDs.

Never writes/retries/changes lifecycle. Bound result is NOT an auto-close proof.
"""
import json
from weex_live_unresolved_local_evidence import local_records
from weex_live_worker import Reader,ROOT

def run():
    reader=Reader(ROOT)
    positions,regular,algos=reader.account()
    rows=[]
    for item in local_records():
        row={'symbol':item['symbol'],'tradeId':item['tradeId'],
             'entryAckPreviouslyVerified':any(w['kind']=='ENTRY' and w['ackSuccess'] and
                w['ackId']==item['entryOrderId'] and w['ackClient']==item['entryClient']
                for w in item['writes']),
             'positionCurrentlyPresent':any(p.get('symbol')==item['symbol'] for p in positions),
             'regularCurrentlyPresent':any(o.get('symbol')==item['symbol'] for o in regular),
             'algosCurrentlyPresent':any(a.get('symbol')==item['symbol'] for a in algos),
             'exitsVerified':False,'canAutoClose':False}
        try:
            order=reader.read('get_capi_v3_order',orderId=item['entryOrderId'])
            if not isinstance(order,dict):raise ValueError('INVALID_EXACT_ORDER')
            row.update(orderHttpReadable=True,
               exactOrderIdMatched=str(order.get('orderId'))==item['entryOrderId'],
               clientIdMatched=order.get('clientOrderId')==item['entryClient'],
               orderSymbolMatched=order.get('symbol')==item['symbol'],
               orderStatus=order.get('status'),
               executedQty=str(order.get('executedQty') or ''),
               reduceOnly=order.get('reduceOnly'))
        except Exception as e:
            row['orderReadErrorType']=type(e).__name__
        try:
            trades=reader.read('get_capi_v3_userTrades',
                               symbol=item['symbol'],orderId=item['entryOrderId'],limit=100)
            if not isinstance(trades,list):raise ValueError('INVALID_FILL_LIST')
            row.update(fillRows=len(trades),fillsPageComplete=len(trades)<100,
                       mismatchedOrderIds=sum(str(t.get('orderId'))!=item['entryOrderId']
                              for t in trades),
                       tradeIdsUnique=len({str(t.get('id')) for t in trades})==len(trades))
        except Exception as e:
            row['fillReadErrorType']=type(e).__name__
        rows.append(row)
    return {'source':'WEEX_LIVE_GET_ONLY','rows':rows,'canClearLifecycle':False,
            'canSubmit':False,'writes':0}
if __name__=='__main__':print(json.dumps(run()))
