"""Bounded GET-only observation of the actual agents on simulation market data."""
import hashlib,json,math,os,sys,time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(r'D:\FUNDSHOT\weex_alerts')
if str(ROOT) not in sys.path:sys.path.append(str(ROOT))
from weex_simulation_cycle import public,read,SIM
from weex_simulation_calibration import inventory
from weex_simulation_depth import assess
from market_agents import analyze
from market_agents_rotating import apply_book_gate
from weex_simple_bot import decide

FOLDER=ROOT/'simulation_domain'/'trigger_and_soak_20261023'
TF={'5m':300000,'15m':900000,'1h':3600000}

def closed_candles(rows,tf,server_ms):
    if not isinstance(rows,list):raise ValueError('INVALID_CANDLE_SCHEMA')
    valid=[];seen=set()
    for row in sorted(rows,key=lambda r:int(r[0])):
        if len(row)<8:raise ValueError('INCOMPLETE_CANDLE')
        start,end=int(row[0]),int(row[6])
        if start in seen or not start<end<=start+TF[tf]:raise ValueError('CANDLE_TIME_INVALID')
        seen.add(start)
        prices=[float(row[i]) for i in (1,2,3,4)];vol=float(row[5])
        if not all(math.isfinite(p) and p>0 for p in prices) or not math.isfinite(vol) or vol<0:
            raise ValueError('CANDLE_VALUES_INVALID')
        op,high,low,close=prices
        if high<max(op,close,low) or low>min(op,close,high):raise ValueError('CANDLE_OHLC_INVALID')
        if end<server_ms:valid.append(row)
    if len(valid)<35:raise ValueError('INSUFFICIENT_CLOSED_CANDLES')
    if server_ms-int(valid[-1][6])>TF[tf]*2:raise ValueError('STALE_CANDLES')
    if any(int(b[0])-int(a[0])!=TF[tf] for a,b in zip(valid,valid[1:])):
        raise ValueError('CANDLE_GAP')
    return valid

def sample(cfg):
    started=time.monotonic()
    tasks={tf:(lambda tf=tf:public('/capi/v3/market/klines',symbol='BTCUSDT',interval=tf,limit=85)) for tf in TF}
    tasks.update(server=lambda:public('/capi/v3/market/time'),
        book=lambda:public('/capi/v3/market/depth',symbol='BTCUSDT',limit=15),
        metadata=lambda:public('/capi/v3/market/exchangeInfo',symbol='BTCUSDT'),
        inventory=lambda:inventory(read))
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        pending={k:pool.submit(fn) for k,fn in tasks.items()}
        data={k:f.result() for k,f in pending.items()}
    server_ms=int(data['server']['serverTime'])
    candles={tf:closed_candles(data[tf],tf,server_ms) for tf in TF}
    meta=next(m for m in data['metadata']['symbols'] if m['symbol']=='BTCUSDT')
    evidence=json.loads((ROOT/'simulation_domain'/'depth_unit_evidence.json').read_text())
    book=assess('BTCUSDT',meta,data['book'],evidence,source_host=SIM)
    def reader(symbol,tf,limit):
        if symbol!='BTCUSDT' or tf not in candles:raise PermissionError('SIMULATION_CANDLE_SCOPE')
        return candles[tf][-limit:]
    market=apply_book_gate(analyze('BTCUSDT',candle_reader=reader),book)
    positions,orders,algos=data['inventory']
    result=decide(market,positions,orders+algos,cfg)
    if result['ordersSubmitted'] is not False or result['decision']!='WAIT':
        raise PermissionError('OBSERVATION_MUST_NOT_ENABLE_ORDERS')
    elapsed=time.monotonic()-started
    if elapsed>15:raise ValueError('SOAK_SNAPSHOT_TOO_SLOW')
    return {'checkedAt':datetime.now(timezone.utc).isoformat(),'snapshotSeconds':round(elapsed,3),
      'serverTime':server_ms,'closedCandleTimes':{tf:candles[tf][-1][6] for tf in TF},
      'bookUpdateId':book.get('bookUpdateId'),'bestAsk':book['bestAsk'],
      'marketSignal':market['marketSignal'],'trend':market['trend'],'momentum':market['momentum'],
      'liquidity':market['liquidity'],'bookPassed':market['realOrderBook']['passed'],
      'positions':len(positions),'ordinaryOrders':len(orders),'conditionalOrders':len(algos),
      'decision':result,'exchangeWrites':0}

def save(report):
    FOLDER.mkdir(parents=True,exist_ok=True)
    tmp=FOLDER/'soak.tmp';target=FOLDER/'soak.json'
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(report,f,indent=2);f.flush();os.fsync(f.fileno())
    tmp.replace(target)

def run():
    path=ROOT/'weex_ai_risk_config.json';original=path.read_bytes();cfg=json.loads(original)
    if cfg['execution']['enabled'] is not False or cfg['execution']['mode']!='PRETRADE':
        raise PermissionError('PRODUCTION_MUST_REMAIN_DISABLED')
    prior=FOLDER/'soak.json'
    if prior.exists():raise PermissionError('SOAK_JOURNAL_ALREADY_EXISTS')
    report={'host':SIM,'status':'RUNNING','plannedSamples':20,'intervalSeconds':15,
        'startedAt':datetime.now(timezone.utc).isoformat(),'samples':[],
        'strategyOrdersEnabled':False,'exchangeWrites':0,'productionConfigSha256':hashlib.sha256(original).hexdigest()}
    save(report)
    for index in range(20):
        start=time.monotonic()
        if path.read_bytes()!=original:raise PermissionError('PRODUCTION_CONFIG_CHANGED')
        try:row=sample(cfg)
        except Exception as exc:row={'errorType':type(exc).__name__,'checkedAt':datetime.now(timezone.utc).isoformat()}
        report['samples'].append(row);save(report)
        print(json.dumps({'sample':index+1,'signal':row.get('marketSignal'),'positions':row.get('positions'),
                          'error':row.get('errorType')}),flush=True)
        if index<19:time.sleep(max(0,15-(time.monotonic()-start)))
    report['finishedAt']=datetime.now(timezone.utc).isoformat()
    report['errors']=sum('errorType' in row for row in report['samples'])
    report['productionConfigUnchanged']=path.read_bytes()==original
    report['status']='PASS_BOUNDED_READ_ONLY_SOAK' if report['errors']==0 else 'COMPLETED_WITH_ERRORS'
    save(report)
    print(json.dumps({'status':report['status'],'samples':len(report['samples']),'errors':report['errors']}))

if __name__=='__main__':
    if sys.argv[1:]!=['run-read-only']:raise SystemExit('EXPLICIT_READ_ONLY_COMMAND_REQUIRED')
    run()
