"""Rotating WEEX market diagnostics with independent real order-book veto; no orders."""
import json,os,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime,timezone
from market_agents import analyze,SIGNAL_PROFILE
from orderbook_liquidity import inspect
from weex_ai_universe import api_trading_symbols
from weex_scan_data import PublicData
from weex_execution_cycle import exclusive
ROOT=Path(__file__).resolve().parent
STATE=ROOT/"market_rotation_state.json"
OUT=ROOT/"market_agents_latest.json"
BATCH=16

def apply_book_gate(result,book):
 """Preserve the analytical signal and report the actual liquidity veto."""
 result=dict(result)
 result["reasons"]=list(result.get("reasons",[]))
 result["marketSignal"]=result.get("decision","WAIT")
 spread=book.get("spreadBps")
 verified=book.get("depthUnitVerified") is True
 depth=min(book.get("top15BidNotional") or 0,book.get("top15AskNotional") or 0)
 reasons=[]
 if book.get("status")!="OK":reasons.append("ORDERBOOK_UNAVAILABLE")
 else:
  if spread is None or not 0<=spread<=15:reasons.append("SPREAD_TOO_WIDE")
  if not verified:reasons.append("DEPTH_UNITS_UNVERIFIED")
  elif not depth>=1000:reasons.append("INSUFFICIENT_BOOK_DEPTH")
 passed=not reasons
 result["realOrderBook"]={**book,"minTop15Notional":depth if verified else None,"passed":passed,"vetoReasons":reasons}
 result["liquidity"]={"proxyOnly":False,"passed":passed,"source":"WEEX order book"}
 if not passed:result["decision"]="WAIT"
 result["reasons"].extend(reasons)
 result["orderPermitted"]=False
 return result
def select_batch(symbols,priority,index,batch=BATCH):
 """Recheck evidence-backed markets every cycle; rotate the rest without starvation."""
 symbols=list(dict.fromkeys(symbols));priority=[s for s in symbols if s in set(priority)]
 rest=[s for s in symbols if s not in set(priority)]
 if not symbols:raise ValueError('EMPTY_UNIVERSE')
 count=min(max(1,batch-len(priority)),len(rest))
 start=index%len(rest) if rest else 0
 rotated=[rest[(start+i)%len(rest)] for i in range(count)]
 return priority+rotated,((start+count)%len(rest) if rest else 0),priority,rotated

def run():
 with exclusive(ROOT/'weex_full_scan.lock'):
  # A supervisor restart within this ten-minute cycle must reuse its completed
  # observation, preserving its timestamp and the already-spent API budget.
  try:
   prior=json.loads((ROOT/'market_agents_latest.json').read_text())
   cfg=json.loads((ROOT/'weex_ai_risk_config.json').read_text())
   universe=json.loads((ROOT/'universe_latest.json').read_text())
   minimum=cfg['risk']['minimumLeverage']
   expected={x['symbol'] for x in universe['symbols'] if x['maxLeverageAdvertised']>=minimum}
   age=(datetime.now(timezone.utc)-datetime.fromisoformat(prior['asOf'])).total_seconds()
   # Completion time must not postpone the next scheduled ten-minute scan.
   same_cycle=int(datetime.fromisoformat(prior.get('startedAt',prior['asOf'])).timestamp())//600==int(time.time())//600
   if (prior.get('scanMode')=='FULL_UNIVERSE' and prior.get('analysisComplete') is True
       and prior.get('strategyProfile')==SIGNAL_PROFILE
       and prior.get('minimumLeverage')==minimum and 0<=age<420 and same_cycle
       and {x['symbol'] for x in prior['results']}==expected):
    return prior
  except (OSError,ValueError,KeyError,TypeError):pass
  result=full_scan(ROOT)
  # Existing scheduled scan owns this finite GET-only maintenance cycle.
  # Publish market observations first; their timestamps are never refreshed by it.
  from weex_depth_autovalidation import run_cycle
  try:run_cycle(ROOT,result,data=PublicData(ROOT,deadline_seconds=60))
  except Exception as exc:
   failure={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'ERROR','reason':type(exc).__name__}
   (ROOT/'weex_depth_autovalidation_latest.json').write_text(json.dumps(failure),encoding='utf-8')
  return result

def full_scan(root,*,data=None,analyzer=analyze,book_reader=inspect):
 from weex_scan_notifications import started as notify_start,finished as notify_finish,failed as notify_failure
 root=Path(root);started=datetime.now(timezone.utc).isoformat()
 def emit(fn,*args):
  try:fn(root,started,*args)
  except Exception as exc:print('SCAN_NOTIFICATION_QUEUE_ERROR '+type(exc).__name__,flush=True)
 emit(notify_start)
 try:result=_full_scan(root,started,data=data,analyzer=analyzer,book_reader=book_reader)
 except Exception as exc:
  emit(notify_failure,exc);raise
 emit(notify_finish,result)
 return result

def _full_scan(root,started,*,data=None,analyzer=analyze,book_reader=inspect):
 root=Path(root);clock=time.monotonic()
 data=data or PublicData(root)
 universe=json.loads((root/'universe_latest.json').read_text(encoding='utf-8'))
 if (datetime.now(timezone.utc)-datetime.fromisoformat(universe['scannedAt'])).total_seconds()>93600:
  raise ValueError('UNIVERSE_STALE')
 allowed=data.get('/capi/v3/market/apiTradingSymbols')
 if not isinstance(allowed,list) or not allowed or any(not isinstance(s,str) for s in allowed):raise ValueError('INVALID_API_UNIVERSE')
 minimum=json.loads((root/'weex_ai_risk_config.json').read_text())['risk']['minimumLeverage']
 symbols=list(dict.fromkeys(x['symbol'] for x in universe['symbols'] if x['symbol'] in set(allowed) and x['maxLeverageAdvertised']>=minimum))
 if not symbols:raise ValueError('EMPTY_ELIGIBLE_UNIVERSE')
 try:priority=json.loads((root/'weex_depth_unit_evidence.json').read_text()).get('symbols',{})
 except (OSError,ValueError):priority={}
 # Enlarging evidence coverage must not add book polling for every WAIT signal.
 priority={s:priority[s] for s in ('BTCUSDT','ETHUSDT','SOLUSDT','1000PEPEUSDT') if s in priority}
 def analyze_one(symbol):
  try:return analyzer(symbol,candle_reader=data.candles)
  except Exception as exc:return {'symbol':symbol,'decision':'ERROR','error':type(exc).__name__,'orderPermitted':False}
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(analyze_one,symbols))
 # Complete all signal analysis before spending the remaining budget on books.
 selected=sorted([row for row in results if row.get('decision')!='ERROR' and (row.get('decision') in ('LONG','SHORT') or row['symbol'] in priority)],
                 key=lambda row:(row['symbol'] not in priority,-row.get('momentum',{}).get('volumeRatio',0)))
 books={}
 for row in selected:
  try:books[row['symbol']]=book_reader(row['symbol'],opener=data.open)
  except Exception as exc:books[row['symbol']]={'status':'ERROR','reason':type(exc).__name__}
 finished=[]
 for row in results:
  if row.get('decision')=='ERROR':finished.append(row);continue
  if row['symbol'] in books:finished.append(apply_book_gate(row,books[row['symbol']]))
  else:
   row={**row,'marketSignal':row['decision'],'orderPermitted':False,
        'realOrderBook':{'status':'NOT_REQUIRED_NO_SIGNAL','passed':False,'depthUnitVerified':False},
        'liquidity':{'proxyOnly':False,'passed':False,'source':'No entry signal; book not requested'}}
   finished.append(row)
 payload={'asOf':datetime.now(timezone.utc).isoformat(),'startedAt':started,
          'agentName':'WEEX full universe scanner','status':'DIAGNOSTIC_ONLY','liveTrading':False,
          'scanMode':'FULL_UNIVERSE','strategyProfile':SIGNAL_PROFILE,'scanIntervalMinutes':10,'minimumLeverage':minimum,
          'universeSize':len(symbols),'results':finished,'prioritySymbols':[x for x in symbols if x in priority],
          'rotatingSymbols':[],'batchStart':0,'durationSeconds':round(time.monotonic()-clock,3),
          'analysisComplete':all(x.get('decision')!='ERROR' for x in finished),'budget':data.stats(),
          'booksRequested':len(selected),'booksUnavailable':sum(x.get('status')!='OK' for x in books.values())}
 target=root/'market_agents_latest.json';tmp=target.with_suffix('.tmp')
 tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8');os.replace(tmp,target)
 return payload

if __name__=='__main__':
 x=run();print('full scan',len(x['results']),'of',x['universeSize'],'complete',x['analysisComplete'],'seconds',x['durationSeconds'],'budget',x['budget'])
