"""Join actual scanner, risk and runner observations. No order or messaging pathway."""
import json,os
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def load(n):return json.loads((ROOT/n).read_text(encoding='utf-8'))
def optional(n):
    try:return load(n)
    except (OSError,ValueError,KeyError):return {}
def recent(stamp,limit=7):
    try:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace('Z','+00:00'))).total_seconds()
        return 0<=age<=limit*60
    except (ValueError,TypeError,AttributeError):return False

def cycle():
    cfg=load('weex_ai_risk_config.json');market=load('market_agents_latest.json')
    positions=optional('position_manager_integrated_latest.json')
    pretrade=optional('weex_simple_bot_latest.json');execution=optional('weex_execution_cycle_latest.json')
    release=optional('live_release_gate_latest.json')
    matching=(pretrade.get('sourceMarketAt')==market.get('asOf')
              and execution.get('scanAt')==pretrade.get('checkedAt'))
    fresh=(recent(market.get('asOf'),12) and recent(positions.get('asOf'),15)
           and recent(pretrade.get('checkedAt'),12) and recent(execution.get('checkedAt'),7))
    allowed=(cfg.get('execution',{}).get('enabled') is False
             and cfg.get('execution',{}).get('mode','PRETRADE')=='PRETRADE'
             and cfg.get('risk',{}).get('marginModePreference')=='cross')
    plans={r.get('symbol'):r for r in pretrade.get('results',[]) if isinstance(r,dict)}
    checks={r.get('tradeId'):r for r in execution.get('results',[]) if isinstance(r,dict)}
    local=pretrade.get('diagnosticPolicy')=='CHECK_ONCE_IN_LIVE_WORKER'
    by_symbol={r.get('symbol'):r for r in execution.get('results',[]) if isinstance(r,dict)}
    result=[]
    for r in market.get('results',[]):
        symbol=r.get('symbol');p=plans.get(symbol,{})
        trend=r.get('trend',{}).get('aligned') is True
        momentum=r.get('momentum',{}).get('confirmed') is True
        liquidity=(r.get('realOrderBook',{}).get('passed') is True
                   and r.get('realOrderBook',{}).get('depthUnitVerified') is True)
        signal=r.get('marketSignal',r.get('decision'))
        candidate=signal in ('LONG','SHORT') and trend and momentum and liquidity
        check=(by_symbol.get(symbol,{}) if local else checks.get((p.get('lifecycle') or {}).get('tradeId'),{})) if matching else {}
        reasons=[x for x in p.get('reasons',[]) if x!='LIVE_EXECUTION_OFF']
        if p.get('plan',{}).get('status')=='BLOCKED_RULES':reasons.append(p['plan'].get('reason','PLAN_RULES_BLOCKED'))
        risk=('ERROR' if p.get('plan',{}).get('status')=='ERROR' or p.get('persistentIntent',{}).get('state')=='BLOCKED' else
              'BLOCKED' if reasons and signal in ('LONG','SHORT') else
              'CHECKED_NO_SIGNAL' if signal=='WAIT' and symbol in plans else
              'CHECKED_PRETRADE' if symbol in plans else 'MISSING')
        result.append({'symbol':symbol,'marketSignal':signal,'trendAgent':trend,
            'momentumAgent':momentum,'liquidityAgent':liquidity,
            'strategyAgent':'CANDIDATE' if candidate and fresh and matching else 'WAIT',
            'riskGuardian':risk,'riskReasons':reasons,
            'executionAgent':check.get('state','AWAITING_PREVIEW' if candidate else 'WAIT_NO_ELIGIBLE_SIGNAL'),
            'executionReason':check.get('reason',check.get('error')),
            'positionManager':'OBSERVE_ONLY','exitAgent':'AWAITING_CONFIRMED_FILL',
            'closedCandleTimes':r.get('closedCandleTimes'),'orderSubmitted':False})
    complete=(bool(result) and positions.get('completeWithinBounds') is True and positions.get('exchangeWrites') is False
              and pretrade.get('ordersSubmitted') is False and execution.get('exchangeWrites')==0
              and all(r['symbol'] in plans for r in result)
              and all(r.get('decision')!='ERROR' for r in market.get('results',[]))
              and all(r['riskGuardian']!='ERROR' for r in result))
    ok=allowed and fresh and matching and complete and execution.get('status')=='OK'
    deferred=pretrade.get('status') in ('WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION') and execution.get('status')==pretrade.get('status')
    state={'checkedAt':datetime.now(timezone.utc).isoformat(),'mode':'SHADOW_ONLY',
        'diagnosticPolicy':pretrade.get('diagnosticPolicy'),'entryChecksPerformed':False if local else None,
        'operatingMode':'INTEGRATED_PRETRADE_VALIDATION','configSafe':allowed,'inputFresh':fresh,
        'sourceBatchesMatch':matching,'inputComplete':complete,'releaseGate':release.get('gate','UNKNOWN'),
        'marketBatch':len(result),'signals':result,'ordersSubmitted':False,'liveReady':False,
        'manualPositionsUntouched':True,'cycleStatus':'OK' if ok else pretrade['status'] if deferred and allowed and recent(pretrade.get('checkedAt'),12) else 'DEGRADED',
        'sourceMarketAt':market.get('asOf'),'sourcePositionsAt':positions.get('asOf'),
        'sourcePretradeAt':pretrade.get('checkedAt'),'sourceExecutionAt':execution.get('checkedAt'),
        'validatedCandidates':sum(r['executionAgent']=='VALIDATED_NOT_SUBMITTED' for r in result)}
    out=ROOT/'weex_agent_orchestrator_latest.json';tmp=out.with_suffix('.tmp')
    tmp.write_text(json.dumps(state,indent=2),encoding='utf-8');os.replace(tmp,out)
    return state

if __name__=='__main__':
    r=cycle();print(r['cycleStatus'],r['operatingMode'],'symbols',r['marketBatch'],'fresh',r['inputFresh'],'orders',r['ordersSubmitted'])
    if r['cycleStatus'] not in ('OK','WAIT_API_BUDGET','WAIT_ACCOUNT_OBSERVATION'):raise SystemExit(1)
