"""Check WEEX agent diagnostic freshness; read-only and fail-closed."""

import json,sqlite3

from contextlib import closing

from pathlib import Path

from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent

DB=ROOT/"market_agent_telemetry.sqlite3"

def assess(now=None):

 now=now or datetime.now(timezone.utc)

 state={"checkedAt":now.isoformat(),"agent":"market_diagnostics","status":"ERROR","reason":"Missing heartbeat","lastSeen":None}

 try:

  with closing(sqlite3.connect(f"file:{DB.as_posix()}?mode=ro",uri=True)) as db:

   row=db.execute("SELECT observed_at,state,detail FROM heartbeat WHERE agent=?",("market_diagnostics",)).fetchone()

  if not row:return state

  dt=datetime.fromisoformat(row[0].replace("Z","+00:00"))

  hours=(now-dt).total_seconds()/3600

  state.update(lastSeen=row[0],hoursSinceHeartbeat=round(hours,3),lastState=row[1],detail=row[2])

  if hours<0:state.update(status="ERROR",reason="Heartbeat in future")

  elif hours>12/60:state.update(status="STALE",reason="Heartbeat older than 12 minutes")
  elif row[1]!="OBSERVED":state.update(status="ERROR",reason="Unexpected heartbeat state")

  else:
   cycle=load_report('weex_execution_cycle_latest.json')
   orchestration=load_report('weex_agent_orchestrator_latest.json')
   positions=load_report('position_manager_integrated_latest.json')
   if not is_recent(cycle,'checkedAt',7,now) or not is_recent(orchestration,'checkedAt',12,now) or not is_recent(positions,'asOf',10,now):
    state.update(status='STALE',reason='Execution, orchestration or position report stale')
   elif (cycle.get('status') in ('WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION')
         and orchestration.get('cycleStatus')==cycle.get('status')
         and cycle.get('exchangeWrites')==0 and orchestration.get('ordersSubmitted') is False
         and positions.get('completeWithinBounds') is True):
    state.update(status=cycle['status'],reason='Diagnostic cycle waiting; entry checks not completed')
   elif cycle.get('status')!='OK' or orchestration.get('cycleStatus')!='OK' or positions.get('completeWithinBounds') is not True:
    state.update(status='ERROR',reason='Execution, orchestration or position audit degraded')
   elif cycle.get('exchangeWrites')!=0 or orchestration.get('ordersSubmitted') is not False:
    state.update(status='ERROR',reason='Unexpected execution write state')
   else:state.update(status="OK",reason="Market, execution, orchestration and position audit fresh")
 except Exception as exc:state.update(status="ERROR",reason=type(exc).__name__)

 return state



def load_report(name):

 try:

  value=json.loads((ROOT/name).read_text(encoding='utf-8'))

  return value if isinstance(value,dict) else {}

 except (OSError,ValueError):return {}



def is_recent(report,key,minutes,now):

 try:

  timestamp=datetime.fromisoformat(report[key].replace('Z','+00:00'))

  age=(now-timestamp).total_seconds()

  return 0<=age<=minutes*60

 except (KeyError,TypeError,ValueError,AttributeError):return False



def assess_agents(now=None):

 """Readiness derives from observations; a WAIT signal is not a broken agent."""

 now=now or datetime.now(timezone.utc)

 market=load_report('market_agents_latest.json')

 pretrade=load_report('weex_simple_bot_latest.json')

 universe=load_report('universe_latest.json')

 positions=load_report('position_manager_integrated_latest.json')

 shadow=load_report('weex_agent_orchestrator_latest.json')

 cfg=load_report('weex_ai_risk_config.json')

 rows=market.get('results',[])

 rows=rows if isinstance(rows,list) else []

 rows=[r for r in rows if isinstance(r,dict)]

 plans=pretrade.get('results',[])

 plans=plans if isinstance(plans,list) else []

 plans=[r for r in plans if isinstance(r,dict)]

 fresh=is_recent(market,'asOf',12,now)
 plan_fresh=is_recent(pretrade,'checkedAt',12,now)
 total=len(rows)

 states={}

 def record(name,state,detail,count=None):

  states[name]={'state':state,'detail':detail,'readyForLive':False}

  if count is not None:states[name]['observations']=count

 def observation_state(count):

  if not fresh:return 'STALE'

  return 'READY_ANALYSIS' if total and count==total else 'DEGRADED' if count else 'MISSING'

 universe_ok=is_recent(universe,'scannedAt',26*60,now) and universe.get('count',0)>0 and universe.get('apiTradingSymbolsChecked') is True

 record('scanner','READY_ANALYSIS' if universe_ok and fresh and market.get('analysisComplete',True) else 'DEGRADED' if universe_ok and fresh else 'STALE',

        'Universo filtrato sulle coppie API; scansione completa ogni 10 minuti.',total)

 for key in ('trend','momentum'):

  count=sum(isinstance(r.get(key),dict) for r in rows)

  record(key,observation_state(count),'Modulo deterministico dello scanner, non processo AI separato.',count)

 books=[r.get('realOrderBook',{}) for r in rows if isinstance(r.get('realOrderBook',{}),dict)]

 observed=sum(b.get('status')=='OK' for b in books)

 verified=sum(b.get('status')=='OK' and b.get('depthUnitVerified') is True for b in books)

 liquid=sum(b.get('passed') is True for b in books)

 liquid_state=observation_state(observed)

 if fresh and observed and verified<observed:liquid_state='PARTIAL_COVERAGE' if verified else 'BLOCKED_UNITS'
 record('liquidity',liquid_state,'Lettura book distinta da unita verificate e liquidita sufficiente.',observed)

 states['liquidity'].update(unitsVerified=verified,liquidityPassed=liquid)
 states['liquidity']['verifiedSymbols']=[r.get('symbol') for r in rows if r.get('realOrderBook',{}).get('depthUnitVerified') is True]
 count=sum(r.get('marketSignal',r.get('decision')) in ('LONG','SHORT','WAIT') for r in rows)

 record('strategy',observation_state(count),'LONG/SHORT/WAIT calcolati; WAIT puo essere un esito valido.',count)

 risk_ok=plan_fresh and pretrade.get('mode')=='READ_ONLY_PREVIEW' and pretrade.get('ordersSubmitted') is False and type(pretrade.get('positionCount')) is int and type(pretrade.get('openOrderCount')) is int

 errors=sum(r.get('plan',{}).get('status')=='ERROR' or r.get('marketSignal')=='ERROR'

            or r.get('persistentIntent',{}).get('state')=='BLOCKED' for r in plans)

 record('risk','READY_READ_ONLY' if risk_ok and not errors else 'DEGRADED' if risk_ok else 'STALE',

        'Controlli conto, occupazione simboli, limiti e preparazione; nessuna autorizzazione agli ordini.',len(plans))

 disabled=cfg.get('execution',{}).get('enabled') is False

 record('execution','VALIDATION_ONLY' if disabled else 'CONFIG_UNSAFE',

        'Runner automatico: controlli freschi e serializzazione senza invio; esecuzione reale non attiva.')

 states['execution']['lifecycleObserved']=plan_fresh and pretrade.get('lifecycle',{}).get('mode')=='PRETRADE'

 states['execution']['liveCycleVerified']=False

 cycle=load_report('weex_execution_cycle_latest.json')

 cycle_fresh=is_recent(cycle,'checkedAt',7,now)

 states['execution']['automaticCycleObserved']=cycle_fresh and cycle.get('status')=='OK' and cycle.get('exchangeWrites')==0
 if disabled and not states['execution']['automaticCycleObserved']:
  states['execution']['state']='DEGRADED' if cycle_fresh else 'STALE'
 states['execution']['automaticCycleAt']=cycle.get('checkedAt')

 states['execution']['validationResults']=cycle.get('results',[])

 states['execution']['scanIssue']=cycle.get('scanIssue')

 journal=pretrade.get('executionJournal',{})

 states['execution']['journalObserved']=plan_fresh and journal.get('environment')=='READ_ONLY'

 states['execution']['registeredIntents']=journal.get('total',0)

 tp_plans=sum(r.get('plan',{}).get('status')=='BLOCKED_PREVIEW' and bool(r['plan'].get('orderPreview',{}).get('tpTriggerPrice')) for r in plans)

 record('exit','PREVIEW_ONLY' if plan_fresh and tp_plans else 'NOT_OBSERVED' if plan_fresh else 'STALE',

        'TP dedicato reduce-only predisposto su fill confermati; ciclo exchange non collaudato.',tp_plans)

 pos_ok=is_recent(positions,'asOf',10,now) and positions.get('completeWithinBounds') is True and positions.get('exchangeWrites') is False
 record('positions','READY_READ_ONLY' if pos_ok else 'STALE_OR_INCOMPLETE',

        'Posizioni e protezioni osservate; posizioni manuali escluse dalle modifiche.',positions.get('positions'))

 shadow_ok=is_recent(shadow,'checkedAt',12,now) and shadow.get('cycleStatus')=='OK' and shadow.get('mode')=='SHADOW_ONLY' and shadow.get('ordersSubmitted') is False and shadow.get('sourceMarketAt')==market.get('asOf')
 record('orchestrator','READY_SHADOW' if shadow_ok else 'STALE_OR_DEGRADED',

        'Coordinamento in shadow, senza invio di ordini.')

 analysis_ok=all(states[k]['state']=='READY_ANALYSIS' for k in ('scanner','trend','momentum','strategy')) and total>0 and (market.get('analysisComplete') is True if market.get('scanMode')=='FULL_UNIVERSE' else observed==total)

 setup=load_report('weex_account_setup_audit_latest.json')

 setup_rows=setup.get('results',[])

 setup_ok=(is_recent(setup,'checkedAt',60,now) and setup.get('allConfigured') is True

           and isinstance(setup_rows,list) and bool(setup_rows) and not setup.get('readErrors')

           and all(isinstance(r,dict) and r.get('matches') is True for r in setup_rows))

 local=pretrade.get('diagnosticPolicy')=='CHECK_ONCE_IN_LIVE_WORKER'
 if local and plan_fresh:
  if pretrade.get('status') in ('WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION'):
   states['risk']['state']=pretrade['status']
  elif risk_ok and not errors:
   states['risk'].update(state='ENTRY_CHECKS_PENDING',detail='Osservazione conto condivisa; leva, commissioni e dimensionamento verificati dal runner prima di ogni ingresso.')
  if cycle_fresh and cycle.get('status')=='OK':
   states['execution'].update(state='ENTRY_CHECKS_PENDING',detail='Diagnostica locale aggiornata; verifica completa demandata al runner live prima dell invio.')
  elif cycle_fresh and cycle.get('status') in ('WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION'):
   states['execution']['state']=cycle['status']
  states['exit'].update(state='ON_CONFIRMED_FILL',detail='Nuovi TP solo dopo fill confermato; i TP esistenti sono verificati nel controllo posizioni.')

 states['risk']['accountLeverageAuditMatches']=setup_ok

 states['risk']['accountLeverageAuditAt']=setup.get('checkedAt')

 states['risk']['leverageReadbackRequiredBeforeEachEntry']=True

 return {'checkedAt':now.isoformat(),'mode':'PRETRADE_NO_ORDERS','modules':states,

         'analysisReady':analysis_ok,'pretradeReady':analysis_ok and risk_ok and not errors and pos_ok and verified==total,

         'liveReady':False,'executionDisabled':disabled,'ordersSubmitted':False,

         'sources':{'marketAt':market.get('asOf'),'pretradeAt':pretrade.get('checkedAt'),'positionsAt':positions.get('asOf')},

         'remainingLiveRequirements':['DEPTH_UNITS_VERIFICATION']+([] if setup_ok else ['ACCOUNT_LEVERAGE_CONFIRMATION'])+['PERSISTENT_EXECUTOR_LIVE_VALIDATION','EXCHANGE_TP_AND_CLOSE_VALIDATION','OPERATOR_LIVE_ACTIVATION_AFTER_VALIDATION']}

def write_status():

 x=assess();t=ROOT/"agent_health.tmp"

 t.write_text(json.dumps(x,indent=2),encoding="utf-8")

 t.replace(ROOT/"agent_health_latest.json")

 agents=assess_agents()

 target=ROOT/'agents_readiness_latest.json';temp=target.with_suffix('.tmp')

 temp.write_text(json.dumps(agents,indent=2),encoding='utf-8');temp.replace(target)

 return x

if __name__=="__main__":

 x=write_status();print(x["status"],x["reason"])

