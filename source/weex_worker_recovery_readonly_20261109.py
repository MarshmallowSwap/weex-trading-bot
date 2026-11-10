"""Read-only, fail-closed recovery audit for WEEX production worker UNKNOWN entry.

Not an execution adapter: cannot place, cancel or close orders and cannot
certify real crash injection. Uses exact durable SQLite journal identities,
authenticated exchange GET data, and current position/TP readback.
"""
import json,sqlite3
from pathlib import Path
from contextlib import closing
from decimal import Decimal as D,InvalidOperation
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
def val(x):
 try:
  d=D(str(x))
  return d if d.is_finite() and d>=0 else None
 except (InvalidOperation,TypeError,ValueError):return None

def classify(item,writes,orders,positions,algos,*,complete):
 tid=item['id'];symbol=item['symbol'];plan=item.get('plan') or {}
 entry=plan.get('entry') or {};intent=writes.get('ENTRY') or {}
 base={'tradeId':tid,'symbol':symbol,'clientOrderId':tid,'safeToResendEntry':False,
       'mayChangeExchange':False,'recoveryRequiresOperator':True}
 def out(state,why,**e):return dict(base,recoveryState=state,reason=why,**e)
 if intent.get('state') not in ('UNKNOWN','RESPONSE_RECEIVED'):
  return out('BLOCKED','NO_PERSISTED_ENTRY_ATTEMPT')
 if intent.get('operation')!='post_capi_v3_order' or intent.get('payload')!=entry:
  return out('BLOCKED','DURABLE_ENTRY_PAYLOAD_NOT_EXACT')
 if not complete or not all(isinstance(x,list) for x in (orders,positions,algos)):
  return out('BLOCKED','INCOMPLETE_EXCHANGE_READBACK')
 if any(not isinstance(x,dict) for x in orders+positions+algos):
  return out('BLOCKED','INVALID_EXCHANGE_READBACK')
 matches=[o for o in orders if o.get('clientOrderId')==tid]
 if len(matches)==0:return out('UNRESOLVED','EXACT_ENTRY_NOT_FOUND_NO_RETRY')
 if len(matches)!=1:return out('BLOCKED','DUPLICATE_CLIENT_ORDER_ID')
 o=matches[0]
 oid=o.get('orderId')
 qty=val(o.get('executedQty'));expected=val(entry.get('quantity'))
 if (not oid or o.get('symbol')!=symbol
     or any(o.get(k)!=entry.get(k) for k in ('side','positionSide','type'))
     or expected is None or expected==0 or qty is None or qty>expected
     or o.get('status') not in ('FILLED','CANCELED','EXPIRED','REJECTED')):
  return out('BLOCKED','ENTRY_ORDER_NOT_CORROBORATED',orderId=str(oid or ''))
 if qty==0:return out('REJECTED_CONFIRMED','TERMINAL_ZERO_FILL',orderId=str(oid))
 if o.get('status')=='FILLED' and qty!=expected:
  return out('BLOCKED','FILLED_QUANTITY_MISMATCH',orderId=str(oid))
 own=[p for p in positions if p.get('symbol')==symbol]
 if len(own)!=1:
  return out('BLOCKED','OPEN_POSITION_MISSING_OR_AMBIGUOUS',orderId=str(oid))
 p=own[0]
 if (not p.get('id') or p.get('side')!=entry.get('positionSide')
     or p.get('marginType')!='CROSSED'
     or val(p.get('size'))!=qty):
  return out('BLOCKED','POSITION_IDENTITY_OR_SIZE_MISMATCH',orderId=str(oid))
 desired=plan.get('tpClientId')
 relevant=[a for a in algos if a.get('symbol')==symbol]
 exact=[a for a in relevant if a.get('clientAlgoId')==desired]
 if len(exact)!=1 or len(relevant)!=1:
  return out('OPEN_UNPROTECTED_REVIEW','NO_UNIQUE_MATCHING_TP',orderId=str(oid),
             positionId=str(p['id']))
 tp=exact[0]
 if (tp.get('algoStatus') not in ('NEW','UNTRIGGERED') or not tp.get('algoId')
     or tp.get('positionSide')!=entry.get('positionSide')
     or tp.get('side')!=('SELL' if entry.get('positionSide')=='LONG' else 'BUY')
     or tp.get('orderType')!='TAKE_PROFIT_MARKET'
     or tp.get('reduceOnly') is not True
     or tp.get('workingType')!='MARK_PRICE'
     or val(tp.get('quantity'))!=qty):
  return out('OPEN_UNPROTECTED_REVIEW','TP_NOT_CONFIRMED_ACTIVE_OR_EXACT',
             orderId=str(oid),positionId=str(p['id']))
 return out('ENTRY_AND_TP_CORROBORATED','READ_ONLY_EXCHANGE_EVIDENCE',
    orderId=str(oid),positionId=str(p['id']),tpAlgoId=str(tp['algoId']),
    protectedPositionObserved=True)

def get_pending(root=ROOT):
 root=Path(root);db=root/'weex_user_live_lifecycle.sqlite3'
 with closing(sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)) as conn:
  conn.row_factory=sqlite3.Row;conn.execute('PRAGMA query_only=ON')
  trades=[dict(x) for x in conn.execute(
    "SELECT id,symbol,state,plan,created FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')")]
  writes=[dict(x) for x in conn.execute(
    "SELECT trade_id,kind,operation,payload,state FROM writes_v1 WHERE kind='ENTRY'")]
 lookup={w['trade_id']:{'ENTRY':dict(w, payload=json.loads(w['payload']))} for w in writes}
 for t in trades:t['plan']=json.loads(t['plan'])
 return [(t,lookup.get(t['id'],{})) for t in trades if t['id'] in lookup]

def worker_uncertain_entry_guard(root, reader, *, pending=None):
 """Independent read-only veto AFTER worker's normal position recovery.

 Only inspect live unresolved UNKNOWN entry intents. Protected entries remain
 under the worker's existing independent position/TP verifier.
 """
 if pending is None:pending=get_pending(root)
 uncertain=[(t,w) for t,w in pending if
   (w.get('ENTRY') or {}).get('state')=='UNKNOWN'
   and t['state'] not in ('PROTECTED','CLOSED','REJECTED','SUPERSEDED')]
 if not uncertain:
  return {'passNewEntries':True,'uncertainCount':0,'cases':[],
   'readOnly':True,'newExchangeWrites':0}
 rows=[]
 from weex_execution_readonly import pages
 for t,w in uncertain:
  try:
   s=t['symbol'];when=max(0,int(t['created'])-1000)
   history=pages(reader.read,'get_capi_v3_order_history',
     identity='orderId',start=0,symbol=s,startTime=when)
   opened=pages(reader.read,'get_capi_v3_openOrders',
     identity='orderId',start=0,symbol=s)
   account=reader.account()
   if not (len(account)==3 and all(isinstance(g,list) for g in account)):
    raise ValueError('INCOMPLETE_ACCOUNT')
   byid={}
   for o in history+opened:
    oid=str(o.get('orderId'))
    if oid in byid and o!=byid[oid]:
     raise ValueError('CHANGING_ORDER_SNAPSHOT')
    byid[oid]=o
   proof=classify(t,w,list(byid.values()),account[0],account[2],complete=True)
  except Exception as exc:
   proof={'tradeId':t['id'],'symbol':t['symbol'],'recoveryState':'BLOCKED',
    'reason':'READBACK_FAILED_'+type(exc).__name__,
    'safeToResendEntry':False,'mayChangeExchange':False}
  rows.append(proof)
 return {'passNewEntries':False,'uncertainCount':len(uncertain),
    'cases':rows,'readOnly':True,'newExchangeWrites':0}

def run(root=ROOT,reader=None):
 from weex_live_worker import Reader
 import live_control
 root=Path(root)
 if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
  raise PermissionError('READ_ONLY_RECOVERY_REQUIRES_STOPPED_VALID_BUILD')
 pending=get_pending(root)
 if reader is None:reader=Reader(root)
 results=[]
 for t,w in pending:
  try:
   s=t['symbol'];when=max(0,int(t['created'])-1000)
   # Must use all matching historical pages, never trust truncated first page.
   from weex_execution_readonly import pages
   history=pages(reader.read,'get_capi_v3_order_history',
     identity='orderId',start=0,symbol=s,startTime=when)
   opened=pages(reader.read,'get_capi_v3_openOrders',
     identity='orderId',start=0,symbol=s)
   account=reader.account()
   if not (len(account)==3 and all(isinstance(x,list) for x in account)):
    raise ValueError('ACCOUNT_SNAPSHOT_NOT_COMPLETE')
   p,other,algos=account
   # Block duplicate IDs even when seen in both open and historical snapshots
   byid={}
   for o in history+opened:
    oid=str(o.get('orderId'))
    if oid in byid and o!=byid[oid]:
     raise ValueError('INCONSISTENT_ORDER_SNAPSHOTS')
    byid[oid]=o
   result=classify(t,w,list(byid.values()),p,algos,complete=True)
  except Exception as exc:
   result={'tradeId':t['id'],'symbol':t['symbol'],
    'recoveryState':'BLOCKED','reason':'READBACK_FAILED_'+type(exc).__name__,
    'safeToResendEntry':False,'mayChangeExchange':False,'recoveryRequiresOperator':True}
  results.append(result)
 return {'checkedAt':datetime.now(timezone.utc).isoformat(),
  'mode':'READ_ONLY_RECOVERY_AUDIT',
  'pendingEntries':len(pending),'results':results,
  'allEntriesResolved':bool(pending) and all(x['recoveryState'] in ('ENTRY_AND_TP_CORROBORATED','REJECTED_CONFIRMED') for x in results),
  'realCrashCertified':False,'exchangeWrites':0,'automaticRecoveryTrades':0,
  'newLiveEntryAuthorized':False,'workerStillStopped':True}

if __name__=='__main__':
 r=run()
 target=ROOT/'weex_worker_recovery_audit_latest.json';temp=target.with_suffix('.tmp')
 temp.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
 temp.replace(target)
 print(json.dumps(r,ensure_ascii=False))
