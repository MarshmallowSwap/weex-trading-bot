"""One durable execution tick shared by scheduled PRETRADE and offline lifecycle tests.

The installed entry point only constructs a GET-only client and a permanently
disabled write policy. A config toggle cannot turn this worker into a live trader.
"""
import json,os
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from weex_lifecycle import Lifecycle,SDKGateway,dec

TERMINAL={'CLOSED','REJECTED','SUPERSEDED'}


@contextmanager
def exclusive(path):
    """OS-held lock, released even on process death; no stale lock-file takeover."""
    with open(path,'a+b') as handle:
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('CYCLE_ALREADY_RUNNING') from None
        else:
            import fcntl
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('CYCLE_ALREADY_RUNNING') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)


def candidates(report,now=None):
    now=now or datetime.now(timezone.utc)
    try:
        age=(now-datetime.fromisoformat(report['checkedAt'])).total_seconds()
        if not 0<=age<=720 or report.get('mode')!='READ_ONLY_PREVIEW' or report.get('ordersSubmitted') is not False:
            raise ValueError('STALE_OR_INVALID_SCAN')
        found=[]
        for row in sorted(report['results'],key=lambda r:float((r.get('momentum') or {}).get('volumeRatio',0)),reverse=True):
            trade=(row.get('lifecycle') or {}).get('tradeId')
            book=row.get('realOrderBook')
            if isinstance(book,dict) and (book.get('passed') is not True or book.get('depthUnitVerified') is not True):continue
            if trade and row.get('marketSignal') in ('LONG','SHORT') and row.get('plan',{}).get('status')=='BLOCKED_PREVIEW':
                found.append(trade)
        if len(found)!=len(set(found)):raise ValueError('DUPLICATE_SCAN_ENTRY')
        return found,None
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError):return [],'STALE_OR_INVALID_SCAN'


def validate_entries(engine,context_provider,entry_ids):
    """Exercise all entry checks and SDK serialization with no dispatch capability."""
    from weex_http_guard import prepare_sdk_request
    results=[]
    unresolved=[r for r in engine.states() if r['state'] not in TERMINAL|{'PROTECTED'}
                and engine.writes(r['id']).get('ENTRY')]
    for tid in dict.fromkeys(entry_ids):
        row={'tradeId':tid,'phase':'VALIDATION','ordersSubmitted':False}
        if unresolved:
            results.append({**row,'state':'BLOCKED_BY_UNRESOLVED_LIFECYCLE'});continue
        try:
            item=engine.get(tid)
            if item['state'] in TERMINAL or engine.writes(tid).get('ENTRY'):continue
            ctx=context_provider(item)
            engine.guard(item,ctx)
            setup=ctx['symbolConfig'];plan=item['plan']
            ready=(setup.get('marginType')=='CROSSED' and dec(setup.get('crossLeverage'))==dec(plan['requestedLeverage']))
            serialized=prepare_sdk_request('post_capi_v3_order',plan['entry'])
            row.update(state='VALIDATED_NOT_SUBMITTED' if ready else 'ACCOUNT_SETUP_REQUIRED',
                       checkedAt=datetime.now(timezone.utc).isoformat(),entrySdkCheck=serialized,
                       contextAgeMs=int(datetime.now(timezone.utc).timestamp()*1000)-int(ctx['observedAtMs']),
                       setupChanged=False,fillBasedTP='AWAITING_CONFIRMED_FILL')
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            # Validation reasons are local fixed codes; avoid printing network errors/credentials.
            row.update(state='PREFLIGHT_BLOCKED',reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
        except Exception as exc:row.update(state='VALIDATION_ERROR',error=type(exc).__name__)
        results.append(row)
    return results


def tick(engine,context_provider,entry_ids):
    """Recover existing writes before considering this scan's new candidates."""
    results=[];handled=set();needs_review=False
    for item in engine.states():
        if item['state'] in TERMINAL or not engine.writes(item['id']).get('ENTRY'):continue
        try:out=engine.reconcile(item['id'])
        except Exception as exc:out={'state':'RECONCILIATION_PENDING','error':type(exc).__name__}
        results.append({'tradeId':item['id'],'phase':'RECOVERY','state':out['state'],'detail':out.get('detail')})
        handled.add(item['id'])
        if out['state'] not in ('CLOSED','REJECTED','PROTECTED'):needs_review=True
    for tid in dict.fromkeys(entry_ids):
        if tid in handled:continue
        if needs_review:
            results.append({'tradeId':tid,'phase':'ENTRY','state':'BLOCKED_BY_UNRESOLVED_LIFECYCLE'});continue
        try:out=engine.advance(tid,lambda symbol:context_provider(engine.get(tid)))
        except Exception as exc:out={'state':'CYCLE_ITEM_ERROR','error':type(exc).__name__}
        results.append({'tradeId':tid,'phase':'ENTRY','state':out['state'],'reason':out.get('reason'),'error':out.get('error')})
        # A fill/TP may be pending after a successful first entry; defer other entries until resolved.
        if out['state'] not in ('CLOSED','REJECTED','PROTECTED','STOP_BEFORE_SUBMISSION','PREFLIGHT_BLOCKED','SUPERSEDED'):
            needs_review=True
    return results


def unresolved_recoveries(results):
    """A pending fill/protection must not be reported as a healthy finished cycle."""
    settled=TERMINAL|{'PROTECTED'}
    return sum(r.get('phase')=='RECOVERY' and r.get('state') not in settled for r in results)


def run(root=None):
    from weex_simple_bot import make_client,R
    from weex_runtime_preflight import context
    root=Path(root) if root else R
    with exclusive(root/'weex_execution_cycle.lock'):
        def config():
            cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
            # Hard boundary for this installed worker, independent of mutable Telegram settings.
            cfg.setdefault('execution',{}).update(enabled=False,mode='PRETRADE')
            return cfg
        actual=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
        client=make_client();gateway=SDKGateway(client)
        engine=Lifecycle(root/'weex_lifecycle.sqlite3',gateway,config)
        try:scan=json.loads((root/'weex_simple_bot_latest.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):scan={}
        ids,reason=candidates(scan)
        unsafe=actual.get('execution',{}).get('enabled') is not False or actual.get('execution',{}).get('mode')!='PRETRADE'
        # Recovery stays read-only. Fresh candidate validation no longer returns
        # before collecting account/market evidence merely because live is disabled.
        results=tick(engine,lambda item:context(gateway,item),[])
        if unsafe:
            results.extend({'tradeId':tid,'phase':'ENTRY','state':'STOP_BEFORE_SUBMISSION'} for tid in ids)
        elif scan.get('diagnosticPolicy')=='CHECK_ONCE_IN_LIVE_WORKER':
            # The controlled live worker still performs its entire fresh capture.
            # No historical validation is represented as a current preflight.
            results.extend({'symbol':r['symbol'],'phase':'LOCAL_DIAGNOSTIC','state':'ENTRY_CHECKS_PENDING',
                            'ordersSubmitted':False,'freshEntryChecksPerformed':False}
                           for r in scan.get('results',[]) if r.get('marketSignal') in ('LONG','SHORT')
                           and (r.get('realOrderBook') or {}).get('passed') is True)
        else:results.extend(validate_entries(engine,lambda item:context(gateway,item),ids))
        errors=sum(x['state'] in ('CYCLE_ITEM_ERROR','VALIDATION_ERROR','REVIEW_REQUIRED','RECONCILIATION_PENDING') for x in results)
        unresolved=unresolved_recoveries(results)
        local=scan.get('diagnosticPolicy')=='CHECK_ONCE_IN_LIVE_WORKER'
        waiting=scan.get('status') in ('WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION')
        if local and scan.get('status') not in ('OK','WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION'):reason=scan.get('status') or 'INVALID_LOCAL_SCAN'
        report={'checkedAt':datetime.now(timezone.utc).isoformat(),'mode':'PRETRADE',
                'diagnosticPolicy':scan.get('diagnosticPolicy'),'freshEntryChecksPerformed':not local,
                'status':'CONFIG_UNSAFE' if unsafe else 'DEGRADED' if errors or reason or unresolved else scan['status'] if waiting else 'OK',
                'scanAt':scan.get('checkedAt'),'scanIssue':reason,'candidateCount':len(ids),
                'recoveredCount':sum(x['phase']=='RECOVERY' for x in results),'results':results,
                'reconciliationNeededCount':unresolved,
                'liveTransportAvailable':False,'ordersSubmitted':False,'exchangeWrites':0,
                'validationMode':'LOCAL_OBSERVATIONS_FRESH_CHECKS_AT_ENTRY' if local else 'FRESH_ACCOUNT_MARKET_AND_SDK_NO_DISPATCH',
                'validatedCount':sum(x['state']=='VALIDATED_NOT_SUBMITTED' for x in results),
                'polling':'after market scan and every 5 minutes via existing position audit'}
        path=root/'weex_execution_cycle_latest.json';tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');tmp.replace(path)
        return report

if __name__=='__main__':
    result=run()
    print(json.dumps({k:result[k] for k in ('checkedAt','mode','status','candidateCount','recoveredCount','exchangeWrites')}))
    if result['status'] not in ('OK','WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION'):raise SystemExit(1)
