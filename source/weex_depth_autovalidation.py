"""Bounded public GET-only unit evidence renewal, called by the existing scanner.

Empirical lot-grid evidence is collected separately for every symbol. Ambiguous
scales remain blocked; no market order, credentials or new scheduler is used.
"""
import hashlib,json,time,re
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from weex_depth_evidence import fingerprint,verify
from weex_api_budget import background,BudgetDeferred

TTL=7*86400
RENEW=6*86400
MAX_SYMBOLS=2
MAX_SECONDS=45
PATH='/capi/v3/market/'

def stamp(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default
def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(path)

def age(row,evidence,now):
    try:return now-datetime.fromisoformat(row.get('checkedAt',evidence['checkedAt'])).timestamp()
    except (KeyError,ValueError,TypeError):return float('inf')

def choose(symbols,signals,evidence,state,now,invalid=()):
    due=[]
    for s in symbols:
        row=evidence.get('symbols',{}).get(s,{})
        if row and s not in invalid and 0<=age(row,evidence,now)<RENEW:continue
        prev=state.get('symbols',{}).get(s,{})
        if prev.get('retryAt',0)>now and not (s in invalid and prev.get('status')=='VERIFIED'):continue
        due.append(s)
    # One signal priority slot, one oldest-unchecked slot: no starvation.
    oldest=lambda s:(state.get('symbols',{}).get(s,{}).get('attemptedAt',0),s)
    hot=sorted((s for s in due if s in signals),key=lambda s:(-signals[s],oldest(s)))
    picked=hot[:1]
    picked+=sorted((s for s in due if s not in picked),key=oldest)[:MAX_SYMBOLS-len(picked)]
    return picked

def assess(symbol,meta,samples,now):
    if meta['symbol']!=symbol or meta['quoteAsset']!='USDT' or meta['contractType']!='PERPETUAL':
        raise ValueError('UNSUPPORTED_CONTRACT')
    step=D(10)**-int(meta['quantityPrecision']);factor=D(str(meta['contractVal']))
    if not factor.is_finite() or factor<=0:raise ValueError('INVALID_CONTRACT_SIZE')
    levels=[];trades={};ids=[]
    for sample in samples:
        at=datetime.fromisoformat(sample['at']).timestamp()
        # ISO timestamps round to microseconds; Windows can return the same
        # clock tick for the immediately following observation.
        if not -0.000001<=now-at<=60:raise ValueError('SAMPLES_NOT_RECENT')
        book=sample['book'];uid=book['lastUpdateId']
        if isinstance(uid,bool) or not isinstance(uid,int) or uid<=0:raise ValueError('INVALID_UPDATE_ID')
        ids.append(uid)
        for side in ('bids','asks'):
            if not book[side]:raise ValueError('EMPTY_BOOK')
            seen=set()
            for price,quantity in book[side]:
                p,q=D(str(price)),D(str(quantity))
                if not p.is_finite() or not q.is_finite() or p<=0 or q<0 or p in seen:raise ValueError('INVALID_BOOK')
                seen.add(p)
                if q:levels.append((p,q))
        if max(D(str(p)) for p,q in book['bids'])>=min(D(str(p)) for p,q in book['asks']):raise ValueError('CROSSED_BOOK')
        for trade in sample['trades']:
            tid=str(trade['id']);p,q,v=(D(str(trade[k])) for k in ('price','qty','quoteQty'))
            if not all(x.is_finite() and x>0 for x in (p,q,v)):raise ValueError('INVALID_TRADE')
            # The workstation may lag exchange time slightly; reject old batches.
            if not -30<=now-int(trade['time'])/1000<=86400:raise ValueError('STALE_TRADES')
            if tid in trades and trade!=trades[tid]:raise ValueError('TRADE_ID_CONFLICT')
            trades[tid]=trade
    if not trades or min(abs(now-int(t['time'])/1000) for t in trades.values())>600:raise ValueError('NO_RECENT_TRADES')
    stats={'symbol':symbol,'rounds':len(samples),'levels':len(levels),'uniqueTrades':len(trades),
        'depthUpdateIds':ids,'tradeQuoteErrors':sum(abs(D(t['price'])*D(t['qty'])-D(t['quoteQty']))>max(D('0.00000001'),D(t['quoteQty'])*D('0.000001')) for t in trades.values()),
        'rawQuantityStepViolations':sum(q%step!=0 for p,q in levels),
        'contractInterpretationStepViolations':sum((q*factor)%step!=0 for p,q in levels),
        'officiallyConfirmed':False}
    row={'metadata':fingerprint(meta),'restEvidence':stats,'method':'LOT_GRID_ELIMINATES_CONTRACT_COUNTS','checkedAt':stamp(now)}
    evidence={'version':1,'checkedAt':stamp(now),'symbols':{symbol:row}}
    valid,reason=verify(symbol,meta,samples[-1]['book'],evidence,datetime.fromtimestamp(now,timezone.utc))
    return row,valid,reason

def run_cycle(root,scan,*,data,clock=time.time,sleeper=time.sleep):
    root=Path(root);now=clock();started=time.monotonic()
    evidence_path=root/'weex_depth_unit_evidence.json';state_path=root/'weex_depth_autovalidation_state.json'
    evidence=load(evidence_path,{'version':1,'checkedAt':stamp(now),'symbols':{}})
    state=load(state_path,{'symbols':{}})
    cycle=scan['startedAt']
    if state.get('lastCycle')==cycle:return load(root/'weex_depth_autovalidation_latest.json',{'status':'ALREADY_CHECKED'})
    if not 0<=now-datetime.fromisoformat(scan['asOf']).timestamp()<=120:return {'status':'STALE_SCAN'}
    symbols=[x['symbol'] for x in scan['results']]
    signals={x['symbol']:x.get('momentum',{}).get('volumeRatio',0) for x in scan['results'] if x.get('marketSignal') in ('LONG','SHORT')}
    invalid={x['symbol'] for x in scan['results'] if (x.get('realOrderBook') or {}).get('depthUnitStatus') in ('UNIT_METADATA_CHANGED','BOOK_QUANTITY_GRID_CHANGED')}
    picked=choose(symbols,signals,evidence,state,now,invalid)
    # Persist the cycle before GETs. Restarts resume on the next scan, not in a loop.
    state['lastCycle']=cycle;save(state_path,state)
    report={'checkedAt':stamp(now),'scanAt':scan['asOf'],'status':'OK','publicGetOnly':True,
            'eligibleSymbols':len(symbols),'selected':picked,'results':[],'maximumExtraWeight':37,'budgetCeiling':None,'budgetMode':'WEEX_SERVER_LIMITS'}
    if picked:
        try:
            with background():
                meta_rows=data.get(PATH+'exchangeInfo')['symbols']
                metadata={x['symbol']:x for x in meta_rows}
                # This empirical method cannot distinguish contract counts from
                # base quantities when contractVal >= 1. Record that limitation
                # without repeatedly paying for samples that cannot prove it.
                for symbol in symbols:
                    row=evidence.get('symbols',{}).get(symbol,{})
                    if row and symbol not in invalid and 0<=age(row,evidence,now)<RENEW:continue
                    meta=metadata.get(symbol)
                    if meta is None:continue
                    factor=D(str(meta['contractVal']))
                    if factor.is_finite() and factor>=1:
                        old=state.setdefault('symbols',{}).get(symbol,{})
                        if old.get('retryAt',0)>now and old.get('status')=='INCONCLUSIVE':continue
                        result={'symbol':symbol,'status':'INCONCLUSIVE','reason':'REST_LOT_GRID_CANNOT_DISTINGUISH_UNIT','checkedAt':stamp(clock())}
                        state['symbols'][symbol]={'attemptedAt':clock(),'retryAt':clock()+86400,'status':'INCONCLUSIVE'}
                        report['results'].append(result)
                save(state_path,state)
                picked=choose(symbols,signals,evidence,state,now,invalid)
                report['selected']=picked
                for symbol in picked:
                    if time.monotonic()-started>MAX_SECONDS:
                        report['status']='WAIT_TIME_BUDGET';break
                    try:
                        samples=[]
                        for i in range(3):
                            if time.monotonic()-started>MAX_SECONDS:raise TimeoutError('VALIDATION_TIME_LIMIT')
                            book=data.get(PATH+'depth',symbol=symbol,limit=200)
                            trades=data.get(PATH+'trades',symbol=symbol,limit=100)
                            samples.append({'at':stamp(clock()),'book':book,'trades':trades})
                            if i<2:sleeper(.5)
                        checked=clock()
                        raw={'metadata':metadata[symbol],'samples':samples}
                        raw_bytes=json.dumps(raw,sort_keys=True).encode();digest=hashlib.sha256(raw_bytes).hexdigest()
                        archive=root/'weex_depth_evidence_samples';archive.mkdir(exist_ok=True)
                        artifact=archive/(digest+'.json');artifact.write_bytes(raw_bytes)
                        row,valid,reason=assess(symbol,metadata[symbol],samples,checked)
                        if valid:
                            row['sourceSha256']=digest;evidence.setdefault('symbols',{})[symbol]=row
                            # Preserve other rows' original ages: never freshen the whole file.
                            evidence['updatedAt']=stamp(checked)
                            evidence['scope']='Per-symbol empirical evidence, seven-day validity from each original observation; unchanged metadata and live quantity grid required.'
                            save(evidence_path,evidence)
                        result={'symbol':symbol,'status':'VERIFIED' if valid else 'INCONCLUSIVE','reason':reason,'sourceSha256':digest,'checkedAt':stamp(checked)}
                        state.setdefault('symbols',{})[symbol]={'attemptedAt':checked,'retryAt':checked+(RENEW if valid else 86400),'status':result['status']}
                        report['results'].append(result);save(state_path,state)
                    except BudgetDeferred:
                        report['status']='WAIT_API_BUDGET';break
                    except Exception as exc:
                        checked=clock();detail=str(exc)
                        reason=detail if isinstance(exc,ValueError) and re.fullmatch('[A-Z_]{1,80}',detail) else type(exc).__name__
                        report['results'].append({'symbol':symbol,'status':'ERROR','reason':reason})
                        state.setdefault('symbols',{})[symbol]={'attemptedAt':checked,'retryAt':checked+3600,'status':'ERROR'};save(state_path,state)
        except BudgetDeferred:report['status']='WAIT_API_BUDGET'
        except Exception as exc:report.update(status='ERROR',reason=type(exc).__name__)
    report['evidenceCurrentCount']=sum(1 for s in symbols if s in evidence.get('symbols',{}) and 0<=age(evidence['symbols'][s],evidence,clock())<=TTL)
    report['finishedAt']=stamp(clock());save(root/'weex_depth_autovalidation_latest.json',report)
    with (root/'weex_depth_autovalidation_events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(report)+'\n')
    return report
