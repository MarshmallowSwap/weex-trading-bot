"""Read-only exact TP histories for two WEEX unresolved bot entries."""
import json,time
from weex_live_worker import Reader,ROOT
from weex_live_unresolved_local_evidence import local_records
from weex_close_proof import verify_bot_exit
from weex_lifecycle import Lifecycle
def run():
 r=Reader(ROOT);ledger=Lifecycle(ROOT/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
 out=[]
 for t in local_records():
  it=ledger.get(t['tradeId'])
  h=r.read('get_capi_v3_allAlgoOrders',symbol=t['symbol'],
       startTime=it['created']-1000,endTime=int(time.time()*1000),limit=1000)
  o={'symbol':t['symbol'],'historyComplete':isinstance(h,dict) and h.get('hasMore') is False,
     'historyRows':len(h.get('orders',[])) if isinstance(h,dict) else -1,
     'expectedClient':t['tpClient'],'tpAckPresent':any(w['kind']=='TP' and w['ackSuccess'] for w in t['writes'])}
  if isinstance(h,dict):
   o['algos']=[{'algoId':str(a.get('algoId')),'clientMatched':a.get('clientAlgoId')==t['tpClient'],
    'orderType':a.get('orderType'),'status':a.get('algoStatus'),'actualOrderId':str(a.get('actualOrderId') or ''),
    'side':a.get('side'),'positionSide':a.get('positionSide'),'reduceOnly':a.get('reduceOnly'),
    'quantity':str(a.get('quantity') or '')} for a in h.get('orders',[]) if a.get('symbol')==t['symbol']]
  out.append(o)
 return {'rows':out,'writes':0}
if __name__=='__main__':print(json.dumps(run()))
