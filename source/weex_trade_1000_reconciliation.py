"""Checkpointed 1000-trade order identity reconciliation, GET-only.
Snapshot held constant across runs to avoid changing boundaries mid-audit.
Per invocation at most 12 exact-order lookups. NO live gate overrides.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from weex_trades_temporal_1000 import collect
from weex_order_pagination import history
from monitor import query
import live_control
ROOT=Path(__file__).resolve().parent
SNAP=ROOT/'weex_trade_1000_snapshot.json'
CKPT=ROOT/'weex_trade_1000_order_checkpoint.json'
REPORT=ROOT/'weex_trade_1000_reconciliation_latest.json'
def atomic(path,obj):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2),encoding='utf-8');os.replace(tmp,path)
def run(max_order_lookups=12):
 if type(max_order_lookups) is not int or not 0<=max_order_lookups<=20:
  raise ValueError('LOOKUP_BUDGET')
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('LIVE_BOT_NOT_STOPPED_OR_INTEGRITY_ERROR')
 if not SNAP.exists():
  t=collect(target=1000,checkpoint_path=ROOT/'weex_trade_1000_temporal_cursor.json')
  if not t['canCertifyCoverage'] or t['tradeCount']!=1000:
   report={'status':'TRADE_SNAPSHOT_INCOMPLETE',
    'requestedTrades':1000,'collectedTrades':t['tradeCount'],
    'remainingTrades':max(0,1000-t['tradeCount']),
    'boundaryProofs':t['boundaryProofs'],'pagesFetchedThisRun':t['pagesFetched'],
    'checkpointPersisted':(ROOT/'weex_trade_1000_temporal_cursor.json').is_file(),
    'pageFailure':t['paginationFailure'],'all1000TradeOrderIdsVerified':False,
    'financialFillNotionalCertified':False,'fullHistoricalCoverage':False,
    'releaseGateOverride':False,'exchangeWrites':False}
   atomic(REPORT,report);return report
  atomic(SNAP,{'checkedAt':datetime.now(timezone.utc).isoformat(),
    'trades':t['trades'],'tradeCount':t['tradeCount'],
    'boundaryProofs':t['boundaryProofs'],'pagesFetched':t['pagesFetched']})
 source=json.loads(SNAP.read_text(encoding='utf-8'))
 trades=source['trades']
 if len(trades)!=1000 or len({str(t.get('id')) for t in trades})!=1000:
  raise ValueError('INVALID_1000_SNAPSHOT')
 if CKPT.exists(): checkpoint=json.loads(CKPT.read_text(encoding='utf-8'))
 else:checkpoint={'statusByOrder':{},'snapshotAt':source['checkedAt']}
 if checkpoint.get('snapshotAt')!=source['checkedAt']:
  raise ValueError('SNAPSHOT_CHANGED_REQUIRES_NEW_CHECKPOINT')
 if isinstance(checkpoint.get('historyOrders'),list):
  history_rows=checkpoint['historyOrders']
 elif checkpoint.get('statusByOrder'):
  # An earlier run already performed the complete historical snapshot and
  # persisted its exact-ID results. Continue only the outstanding lookups.
  # Do not spend quota re-fetching historical rows merely to resume.
  history_rows=[]
  checkpoint['historyAlreadyClassified']=True
 else:
  try:h=history(max_pages=10)
  except Exception as e:
   if type(e).__name__!='BudgetDeferred':raise
   report={'status':'WAIT_API_BUDGET','requestedTrades':1000,'tradeCount':len(trades),
    'matchedOrders':sum(x.get('matched') is True for x in checkpoint['statusByOrder'].values()),
    'budgetDeferred':True,'all1000TradeOrderIdsVerified':False,
    'financialFillNotionalCertified':False,'fullHistoricalCoverage':False,
    'releaseGateOverride':False,'exchangeWrites':False}
   atomic(REPORT,report);return report
  if not h.get('completeWithinRequestedBounds'):raise ValueError('HISTORY_PAGE_INCOMPLETE')
  history_rows=h['orders']
  checkpoint['historyOrders']=history_rows
  atomic(CKPT,checkpoint)
 orders={str(o['orderId']):o for o in history_rows if isinstance(o,dict) and o.get('orderId')}
 expected={}
 for t in trades:
  oid=str(t.get('orderId'));sym=t.get('symbol')
  if oid in expected and expected[oid]!=sym:
   raise ValueError('CONFLICTING_ORDER_SYMBOLS')
  expected[oid]=sym
 results=checkpoint['statusByOrder']
 for oid,sym in expected.items():
  if oid in orders:
   o=orders[oid]
   results[oid]={'matched':o.get('symbol')==sym,
    'reason':'HISTORY_ORDER_EXACT_ID' if o.get('symbol')==sym else 'ORDER_SYMBOL_CONFLICT'}
 looked=0;deferred=False
 for oid in sorted(expected):
  if oid in results:continue
  if looked>=max_order_lookups:break
  try:
   order=query('/capi/v3/order?orderId='+oid)
   matched=(isinstance(order,dict) and str(order.get('orderId'))==oid
    and order.get('symbol')==expected[oid] and bool(order.get('clientOrderId')))
   results[oid]={'matched':matched,'reason':'EXACT_ORDER_DETAIL' if matched else 'ORDER_DETAIL_INCONSISTENT'}
   looked+=1
  except Exception as e:
   if type(e).__name__=='BudgetDeferred':
    deferred=True;break
   results[oid]={'matched':False,'reason':'READ_FAILED','errorClass':type(e).__name__}
   looked+=1
  atomic(CKPT,checkpoint)
 atomic(CKPT,checkpoint)
 matched_ids={oid for oid,x in results.items() if x.get('matched') is True}
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
  'snapshotAt':source['checkedAt'],'requestedTrades':1000,'tradeCount':len(trades),
  'uniqueOrders':len(expected),'matchedOrders':len(matched_ids & expected.keys()),
  'unresolvedOrders':sum(oid not in results or not results[oid].get('matched') for oid in expected),
  'matchedTrades':sum(str(t['orderId']) in matched_ids for t in trades),
  'unmatchedTrades':sum(str(t['orderId']) not in matched_ids for t in trades),
  'newOrderLookups':looked,'budgetDeferred':deferred,'historyOrdersRead':len(orders),
  'all1000TradeOrderIdsVerified':all(oid in matched_ids for oid in expected),
  'financialFillNotionalCertified':False,'fullHistoricalCoverage':False,
  'releaseGateOverride':False,'exchangeWrites':False}
 atomic(REPORT,report)
 return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
