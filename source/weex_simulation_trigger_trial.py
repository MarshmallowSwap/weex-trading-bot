"""One minimum-size simulated entry, bounded natural TP wait, guaranteed cleanup attempt."""
import hashlib,json,sys,time
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(r'D:\FUNDSHOT\weex_alerts')
if str(ROOT) not in sys.path:sys.path.append(str(ROOT))
import weex_simulation_cycle as c

FOLDER=ROOT/'simulation_domain'/'trigger_and_soak_20261023'
SCOPE='MINIMUM_SIMULATION_NATURAL_TRIGGER_300_SECONDS'

def bind():
    return c.bind(FOLDER)

def prepare(*,engine_factory=None):
    folder=bind()
    if c.base.FILE.exists():raise PermissionError('TRIGGER_JOURNAL_EXISTS_USE_RESUME')
    previous=json.loads((c.FOLDER/'journal.json').read_text())
    if previous['status']!='CLOSED_VERIFIED' or not previous['takeProfitAcceptancePassed'] or any(previous['finalInventory'].values()):
        raise PermissionError('PREVIOUS_TP_CYCLE_NOT_COMPLETE')
    c.base.prepare()
    state=json.loads(c.base.FILE.read_text())
    ctx,rules,meta=c.context()
    if any(ctx[k] for k in ('positions','openOrders','conditionalOrders')):
        raise PermissionError('SIMULATION_ACCOUNT_NOT_EMPTY')
    price=D(ctx['referencePrice']);qty=D('0.0001');fee=D(ctx['exitFeeRate'])
    plan={'orderPreview':state['entry'],'requestedLeverage':'200','beforePositions':[],
      'targetNetProfitUSDT':c.TARGET,'exitFeeRate':str(fee),
      'requiredMarginAndEntryFeeUSDT':str(qty*price/200+qty*price*fee),
      'sizing':{'priceTick':str(rules['priceTick']),'notionalUSDT':str(qty*price)}}
    state.update(createdAt=datetime.now(timezone.utc).isoformat(),cycleScope=SCOPE,
      authorization='User: Procedi, following TP trigger and continuous simulation validation proposal',
      metadataSnapshot=meta,maximumWaitSeconds=300)
    engine=(engine_factory or c.engine_for)(state,folder)
    item=engine.prepare('sim-natural-trigger-'+state['createdAt'],plan)
    state.update(tradeId=item['id'],entry=item['plan']['entry'],testNetTarget=c.TARGET,
      exitTemplate={**state['exitTemplate'],'newClientOrderId':'wxclose_'+item['id'][8:]})
    c.base.save(state);engine.guard(item,ctx)
    print(json.dumps({'status':'PREPARED','host':c.SIM,'quantity':'0.0001','leverage':200,'waitLimitSeconds':300}))

def monitor(state,engine,result,*,clock=time.time,sleep=time.sleep):
    deadline=datetime.fromisoformat(state['deadlineAt']).timestamp()
    consecutive_errors=0
    while True:
        name=result['state']
        state['lastLifecycleState']=name
        state.setdefault('monitoring',[]).append({'at':datetime.now(timezone.utc).isoformat(),
           'state':name,'detail':result.get('detail')})
        if name=='PROTECTED':
            if not state.get('protectedObserved'):
                state['protectedObserved']=True
                state['protectedTpRequest']=engine.get(state['tradeId'])['owned']['tpRequest']
                state['protectedTpObservation']=c.find_tp(state)
            consecutive_errors=0
        elif name=='CLOSED':
            state['naturalCloseLifecycle']=result.get('detail');c.base.save(state);return
        elif name in ('REJECTED','PREFLIGHT_BLOCKED','STOP_BEFORE_SUBMISSION'):
            state['monitorStopReason']=name;c.base.save(state);return
        elif name in ('REVIEW_REQUIRED','RECONCILIATION_PENDING'):
            consecutive_errors+=1
            # Bounded reconciliation also accommodates exchange history propagation.
            if consecutive_errors>=4:
                state['monitorStopReason']='RECONCILIATION_UNRESOLVED';c.base.save(state);return
        c.base.save(state)
        remaining=deadline-clock()
        print(json.dumps({'lifecycleState':name,'secondsRemaining':max(0,round(remaining))}),flush=True)
        if remaining<=0:
            state['monitorStopReason']='DEADLINE_REACHED';c.base.save(state);return
        sleep(min(5,remaining))
        result=engine.reconcile(state['tradeId'])

def execute(*,engine_factory=None):
    folder=bind();state=json.loads(c.base.FILE.read_text())
    if state.get('host')!=c.SIM or state.get('cycleScope')!=SCOPE:raise PermissionError('TRIGGER_SCOPE_REQUIRED')
    if state['status']=='CLOSED_VERIFIED':
        print(json.dumps({'status':state['status'],'repeatEntry':False}));return
    engine=(engine_factory or c.engine_for)(state,folder)
    try:
        if 'ENTRY' not in state['records']:
            if hashlib.sha256((ROOT/'weex_ai_risk_config.json').read_bytes()).hexdigest()!=state['productionConfigSha256']:
                raise PermissionError('PRODUCTION_CONFIG_CHANGED')
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(state['createdAt'])).total_seconds()
            if not 0<=age<=300:raise PermissionError('TRIGGER_PREPARATION_EXPIRED')
            ctx,_,_=c.context()
            state['deadlineAt']=(datetime.now(timezone.utc)+timedelta(seconds=300)).isoformat()
            c.base.save(state)
            result=engine.advance(state['tradeId'],lambda _:ctx)
        else:result=engine.reconcile(state['tradeId'])
        monitor(state,engine,result)
    except Exception as exc:
        state['trialErrorType']=type(exc).__name__
        if type(exc) in (ValueError,PermissionError,RuntimeError):state['trialError']=str(exc)
        c.base.save(state)
    finally:
        if 'ENTRY' in state['records']:c.cleanup(state,engine)
        else:print(json.dumps({'status':'STOPPED_WITHOUT_ORDER','reason':state.get('trialError') or state.get('lastLifecycleState')}))

if __name__=='__main__':
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['execute-authorized']:execute()
        else:raise PermissionError('EXPLICIT_TRIGGER_COMMAND_REQUIRED')
    except Exception as exc:
        print(json.dumps({'status':'REVIEW_REQUIRED','errorType':type(exc).__name__,
          'reason':str(exc) if type(exc) in (ValueError,RuntimeError,PermissionError) else 'SEE_JOURNAL'}))
        raise SystemExit(1)
