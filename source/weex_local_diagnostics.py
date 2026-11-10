"""Publish scanner diagnostics without repeating live preflight network calls."""
import json
from pathlib import Path
from datetime import datetime,timezone
from weex_account_observation import load
from weex_api_budget import BudgetDeferred,Budget

POLICY='CHECK_ONCE_IN_LIVE_WORKER'

def publish(root,cfg,scan_fn,decide_fn):
    root=Path(root)
    if cfg.get('execution',{}).get('enabled') is not False or cfg.get('execution',{}).get('mode')!='PRETRADE':
        raise ValueError('DIAGNOSTIC_PRETRADE_REQUIRED')
    status='OK';reason=None
    try:market=scan_fn()
    except BudgetDeferred as exc:
        market={'results':[],'asOf':None,'analysisComplete':False}
        status='WAIT_API_BUDGET';reason=str(exc)
    observation=load(root,max_age=420)
    p=observation['positions'] if observation else None
    o=observation['regularOrders']+observation['trailingOrders'] if observation else None
    a=observation['conditionalOrders'] if observation else None
    if observation:
        from weex_live_worker import exclude_verified_demo_aliases
        a,_=exclude_verified_demo_aliases(a,p,root)
    if status=='OK' and not market.get('analysisComplete'):status='INCOMPLETE_MARKET'
    failures=[r.get('error') for r in market['results'] if r.get('decision')=='ERROR']
    failures += [(r.get('realOrderBook') or {}).get('reason') for r in market['results']
                 if (r.get('realOrderBook') or {}).get('status')=='ERROR']
    if failures and all(x=='BudgetDeferred' for x in failures):status='WAIT_API_BUDGET'
    if status=='OK' and observation is None:status='WAIT_ACCOUNT_OBSERVATION'
    results=[]
    for row in market['results']:
        decision=decide_fn(row,p,(o+a) if observation else None,cfg)
        result={'symbol':row['symbol'],'marketSignal':row.get('marketSignal',row.get('decision')),
                **decision,'realOrderBook':row.get('realOrderBook'),'momentum':row.get('momentum'),
                'closedCandleTimes':row.get('closedCandleTimes'),'observedAt':row.get('observedAt'),
                'entryChecksPerformed':False,'entryChecksRequired':'FRESH_ACCOUNT_FEES_LEVERAGE_SIZING_BOOK_AT_DISPATCH'}
        if result['marketSignal'] in ('LONG','SHORT'):
            result['plan']={'status':'DEFERRED_TO_LIVE_PREFLIGHT','ordersSubmitted':False}
        results.append(result)
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'sourceMarketAt':market['asOf'],
            'mode':'READ_ONLY_PREVIEW','diagnosticPolicy':POLICY,'status':status,'reason':reason,
            'sourceAccountAt':observation['observedAt'] if observation else None,
            'positionCount':len(p) if observation else None,'openOrderCount':len(o) if observation else None,
            'conditionalOrderCount':len(a) if observation else None,'accountCanTrade':None,
            'entryChecksPerformed':False,'results':results,'ordersSubmitted':False,
            'apiBudget':Budget(root).used(),'lifecycle':{'mode':'PRETRADE','states':[],'liveWritesEnabled':False}}
    target=root/'weex_simple_bot_latest.json';tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');tmp.replace(target)
    return report
