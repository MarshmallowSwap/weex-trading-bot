"""Incremental GET-only WEEX fill economics for bounded FILLED order history.
Scoped recent snapshot; no production order submissions. Pause on rate budget,
persist exact outcomes, never mark incomplete coverage as certified.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from weex_order_pagination import history
from monitor import query
from weex_fill_notional_strict import verify
ROOT=Path(__file__).resolve().parent
PATH=ROOT/'weex_historical_fill_audit_checkpoint.json'
LATEST=ROOT/'weex_historical_fill_audit_latest.json'
def atomic(path,obj):
    t=path.with_suffix('.tmp');t.write_text(json.dumps(obj,indent=2),encoding='utf-8');os.replace(t,path)
def run(max_orders=5):
    if not isinstance(max_orders,int) or not 1<=max_orders<=10:raise ValueError('BOUNDED_AUDIT')
    import live_control
    if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
        raise PermissionError('PRODUCTION_MUST_REMAIN_STOPPED_AND_INTACT')
    listing=history(max_pages=5)
    if listing.get('completeWithinRequestedBounds') is not True:
        raise ValueError('HISTORY_NOT_COMPLETE_WITHIN_BOUNDS')
    targets={(str(x.get('orderId')),x.get('symbol')):x
       for x in listing['orders'] if isinstance(x,dict)
       and x.get('status')=='FILLED' and x.get('orderId') and x.get('symbol')}
    scope=sorted((oid,symbol) for oid,symbol in targets)
    if PATH.exists():
        checkpoint=json.loads(PATH.read_text(encoding='utf-8'))
        if checkpoint.get('scope')!=scope:
            # Never automatically merge results across changed historical windows.
            backup=PATH.with_name('weex_historical_fill_audit_prior.json')
            if backup.exists():raise ValueError('HISTORY_CHANGED_REQUIRES_REVIEW')
            os.replace(PATH,backup)
            checkpoint={'scope':scope,'results':{},'scopeChanged':True}
    else:checkpoint={'scope':scope,'results':{},'scopeChanged':False}
    count=0;deferred=False
    for oid,symbol in scope:
        key=oid+'|'+symbol
        if key in checkpoint['results']:continue
        if count>=max_orders:break
        try:
            order=query('/capi/v3/order?orderId='+oid)
            fills=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
            proof=verify(order,fills)
            checkpoint['results'][key]={
                'verified':proof.get('verified') is True,
                'reason':proof.get('reason'),
                'fillCount':proof.get('fillCount'),
                'notionalUSDT':proof.get('executedFillNotionalUSDT'),
                'feeUSDT':proof.get('executionFeeUSDT'),
                'parentQuoteDeltaUSDT':proof.get('parentOrderQuoteDifferenceUSDT')}
            count+=1
        except Exception as exc:
            if type(exc).__name__=='BudgetDeferred':
                deferred=True;break
            checkpoint['results'][key]={'verified':False,'reason':'READ_FAILED',
                                      'errorClass':type(exc).__name__}
            count+=1
        atomic(PATH,checkpoint)
    audited=len(checkpoint['results'])
    passed=sum(x.get('verified') is True for x in checkpoint['results'].values())
    out={'checkedAt':datetime.now(timezone.utc).isoformat(),
         'scope':'BOUNDED_RECENT_FILLED_ORDER_HISTORY',
         'historyPages':listing['pagesFetched'],'expectedOrders':len(scope),
         'auditedOrders':audited,'verifiedOrders':passed,
         'unresolvedOrders':audited-passed,'remainingOrders':len(scope)-audited,
         'budgetDeferred':deferred,'scopeChanged':checkpoint['scopeChanged'],
         'scopeFullyCovered':audited==len(scope) and bool(scope),
         'scopeAllVerified':audited==passed==len(scope) and bool(scope),
         'fullHistoricalCoverage':False,'releaseGateOverride':False,
         'productionOrdersSent':0,'exchangeWrites':0}
    atomic(LATEST,out)
    return out
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
