"""WEEX LTC exact external conditional close proof, authenticated GET only.

No state mutations, no trading writes, no ownership promotion. The external
exit must be linked to a fully filled reduce-only historical conditional algo,
and full entry+exit fills must match the durable bot entry economics.
"""
import json,time,hashlib
from pathlib import Path
from decimal import Decimal
from weex_live_worker import Reader,ROOT
from weex_lifecycle import Lifecycle
from weex_close_proof import fills,number
TID='wxentry_1566be92f4fe10fdd0b83ca3'
def run(*,persist_evidence=False):
  report={'tradeId':TID,'symbol':'LTCUSDT','status':'NOT_VERIFIED',
          'liveWrites':0,'mayClearJournal':False,'botTPUsed':False}
  engine=Lifecycle(ROOT/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
  item=engine.get(TID);owned=item['owned'];plan=item['plan']
  if item['symbol']!='LTCUSDT' or not owned:raise ValueError('INVALID_LOCAL_SCOPE')
  older=json.loads((ROOT/'ltc_closure_diagnostic.json').read_text(encoding='utf-8'))
  known=older.get('orders',[])
  entries=[x for x in known if str(x.get('orderId'))==str(owned['entryOrderId'])]
  exits=[x for x in known if str(x.get('orderId'))!=str(owned['entryOrderId']) and x.get('reduceOnly') is True]
  if len(entries)!=1 or len(exits)!=1:raise ValueError('UNKNOWN_EXACT_EXIT_ORDER')
  exit_id=str(exits[0]['orderId'])
  reader=Reader(ROOT)
  positions,regular,algos=reader.account()
  if any(x.get('symbol')=='LTCUSDT' for x in positions+regular+algos):
    raise ValueError('LTC_NOT_FLAT_OR_PENDING_ORDER')
  entry=reader.read('get_capi_v3_order',orderId=owned['entryOrderId'])
  exit_order=reader.read('get_capi_v3_order',orderId=exit_id)
  if str(entry.get('orderId'))!=str(owned['entryOrderId']) or entry.get('clientOrderId')!=TID:
    raise ValueError('ENTRY_IDENTITY_MISMATCH')
  side=plan['entry']['side'];position_side=plan['entry']['positionSide']
  if (entry.get('symbol')!='LTCUSDT' or entry.get('side')!=side or
      entry.get('positionSide')!=position_side or entry.get('reduceOnly') is not False
      or entry.get('status')!='FILLED' or entry.get('type')!='MARKET'):
    raise ValueError('ENTRY_NOT_VALID')
  if (str(exit_order.get('orderId'))!=exit_id or exit_order.get('symbol')!='LTCUSDT'
      or exit_order.get('positionSide')!=position_side
      or exit_order.get('side')!=('SELL' if side=='BUY' else 'BUY')
      or exit_order.get('status')!='FILLED' or exit_order.get('type')!='TAKE_PROFIT_MARKET'
      or exit_order.get('reduceOnly') is not True):
    raise ValueError('EXIT_NOT_VALID')
  timestamp=int(entry['time'])
  end=int(time.time()*1000)
  observed=reader.read('get_capi_v3_userTrades',symbol='LTCUSDT',
      startTime=timestamp-60000,endTime=end,limit=100)
  if not isinstance(observed,list) or len(observed)>=100 or len(observed)==0:
    raise ValueError('TRADES_INCOMPLETE_OR_UNKNOWN')
  all_ids={str(x.get('orderId')) for x in observed}
  if all_ids!={str(entry['orderId']),exit_id}:
    raise ValueError('OTHER_SYMBOL_EXECUTION_IN_WINDOW')
  by_order={id:[x for x in observed if str(x['orderId'])==id] for id in all_ids}
  eq,ec,ef=fills(entry,by_order[str(entry['orderId'])])
  xq,xv,xf=fills(exit_order,by_order[exit_id])
  if (eq!=number(owned['quantity']) or xq!=eq or
      ec!=number(owned['actualEntryCostUSDT'])
      or ef!=number(owned['actualEntryFeesUSDT'])):
    raise ValueError('NOT_MATCHED_TO_BOT_ENTRY_ECONOMICS')
  prior=reader.read('get_capi_v3_allAlgoOrders',symbol='LTCUSDT',
      startTime=item['created']-1000,endTime=end,limit=1000)
  if not isinstance(prior,dict) or prior.get('hasMore') is not False or not isinstance(prior.get('orders'),list):
    raise ValueError('ALGO_HISTORY_NOT_COMPLETE')
  relevant=[a for a in prior['orders'] if str(a.get('algoId'))==exit_id or
      str(a.get('actualOrderId') or '')==exit_id]
  if len(relevant)!=1:raise ValueError('EXTERNAL_ALGO_NOT_UNIQUE')
  algo=relevant[0]
  if (algo.get('algoStatus') not in ('FILLED','TRIGGERED') or
      algo.get('reduceOnly') is not True or algo.get('symbol')!='LTCUSDT' or
      algo.get('positionSide')!=position_side or
      algo.get('side')!=exit_order['side'] or
      number(algo.get('quantity'))!=eq or
      algo.get('clientAlgoId')==plan.get('tpClientId')):
    raise ValueError('EXTERNAL_ALGO_CONFLICT_OR_UNVERIFIED')
  if any(p.get('symbol')=='LTCUSDT' for p in plan.get('beforePositions',[])):
    raise ValueError('PREEXISTING_LTC_POSITION')
  pnl=(xv-ec if side=='BUY' else ec-xv)-ef-xf
  raw={'entry':entry,'exit':exit_order,'fills':by_order,'algo':algo}
  report.update(status='EXTERNAL_TP_HISTORICAL_CLOSE_VERIFIED',
    closedQuantity=str(xq),actualExitValueUSDT=str(xv),
    actualExitFeesUSDT=str(xf),netBeforeFundingUSDT=str(pnl),
    targetMetBeforeFunding=pnl>=number(plan['targetNetProfitUSDT']),
    exitOrderId=exit_id,externalAlgoId=str(algo['algoId']),
    checkedAt=int(time.time()*1000),
    evidenceSha256=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest(),
    stillNotBotTP=True,flatAccountConfirmed=True,mayClearJournal=False)
  if persist_evidence:
    target=ROOT/'weex_ltc_verified_close_evidence.json'
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps({'report':report,'raw':raw},indent=2),encoding='utf-8')
    temporary.replace(target)
  return report
if __name__=='__main__':
 try:print(json.dumps(run()))
 except Exception as e:print(json.dumps({'status':'NOT_VERIFIED','errorType':type(e).__name__,
   'reason':str(e) if type(e) is ValueError else None,'liveWrites':0,'mayClearJournal':False}))
