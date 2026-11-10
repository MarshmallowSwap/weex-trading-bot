"""WEEX live historical close evidence: exact order GET per actual fill order ID.

Does not update lifecycle. Uses prior verifier prove() that rejects partial,
unrelated or economics-mismatched fills; never infers from flat account.
"""
from weex_live_worker import Reader,ROOT
from weex_live_unresolved_local_evidence import local_records
from weex_close_proof import prove
from decimal import Decimal
from datetime import datetime,timezone
from pathlib import Path
import json,sqlite3
def read_item(trade_id):
 with sqlite3.connect('file:'+(ROOT/'weex_user_live_lifecycle.sqlite3').resolve().as_posix()+'?mode=ro',uri=True) as c:
  c.row_factory=sqlite3.Row
  row=c.execute('SELECT id,symbol,state,plan,owned,detail FROM trades_v1 WHERE id=?',(trade_id,)).fetchone()
  return {'id':row['id'],'symbol':row['symbol'],'state':row['state'],
    'plan':json.loads(row['plan'] or '{}'),'owned':json.loads(row['owned'] or '{}')}
def run():
 reader=Reader(ROOT)
 positions,regular,algos=reader.account()
 outputs=[]
 for item in local_records():
  entry=reader.read('get_capi_v3_order',orderId=item['entryOrderId'])
  start=int(entry['time'])-60000;end=int(datetime.now(timezone.utc).timestamp()*1000)
  trades=reader.read('get_capi_v3_userTrades',symbol=item['symbol'],
                     startTime=start,endTime=end,limit=100)
  record={'symbol':item['symbol'],'tradeId':item['tradeId'],
          'fillCount':len(trades),'fillsNotTruncated':len(trades)<100,
          'positionFlat':not any(x.get('symbol')==item['symbol'] for x in positions),
          'openOrdersAbsent':not any(x.get('symbol')==item['symbol'] for x in regular+algos),
          'canUpdateJournal':False}
  if len(trades)>=100:record['reason']='FILL_HISTORY_SATURATED';outputs.append(record);continue
  order_ids=sorted({str(x['orderId']) for x in trades})
  orders=[reader.read('get_capi_v3_order',orderId=i) for i in order_ids]
  by_order={str(o['orderId']):[x for x in trades if str(x['orderId'])==str(o['orderId'])] for o in orders}
  record['orders']=[{'orderId':str(o['orderId']),'type':o.get('type'),
       'side':o.get('side'),'status':o.get('status'),
       'reduceOnly':o.get('reduceOnly'),'executedQty':str(o.get('executedQty')),
       'fillRows':len(by_order[str(o['orderId'])])} for o in orders]
  try:
   proof=prove(read_item(item['tradeId']),orders,by_order)
   record['verifier']='PASS'
   record['proof']={k:v for k,v in proof.items() if k not in ('entryOrderId','exitOrderIds')}
   record['exitOrderCount']=len(proof['exitOrderIds'])
  except Exception as e:
   record['verifier']='BLOCKED'
   record['reason']=str(e) if type(e) is ValueError else type(e).__name__
  outputs.append(record)
 return {'source':'WEEX_LIVE_GET_ONLY','rows':outputs,'writes':0,
         'lifecycleChanged':False}
if __name__=='__main__':print(json.dumps(run()))
