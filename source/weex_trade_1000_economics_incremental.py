"""Checkpointed real WEEX per-order economic audit, strictly GET-only.

Each order is independently fetched with its exact fills; do not use the
1000-row snapshot as a complete fill list for boundary orders. No gate bypass.
"""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import os,json
import live_control
from monitor import query
from weex_fill_notional_strict import verify
from weex_api_budget import budget
ROOT=Path(__file__).resolve().parent
SNAP=ROOT/'weex_trade_1000_snapshot.json'
ORDER_CK=ROOT/'weex_trade_1000_order_checkpoint.json'
CK=ROOT/'weex_trade_1000_economics_checkpoint.json'
REPORT=ROOT/'weex_trade_1000_economics_latest.json'
def save(path,doc):
    p=path.with_suffix('.tmp');p.write_text(json.dumps(doc,indent=2),encoding='utf-8');os.replace(p,path)
def run(max_orders=12):
    if type(max_orders) is not int or not 1<=max_orders<=20:raise ValueError('MAX_20')
    if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
        raise PermissionError('PRODUCTION_NOT_STOPPED_OR_BUILD_BAD')
    source=json.loads(SNAP.read_text(encoding='utf-8'))
    ids=json.loads(ORDER_CK.read_text(encoding='utf-8'))
    trades=source['trades']
    if (len(trades)!=1000 or ids['snapshotAt']!=source['checkedAt']
        or len({str(t['id']) for t in trades})!=1000):
        raise ValueError('TRADE_SNAPSHOT_NOT_EXACTLY_1000')
    expected={}
    for t in trades:
        oid=str(t['orderId'])
        if oid in expected and expected[oid]!=t['symbol']:
            raise ValueError('CONFLICTING_ORDER_SYMBOL')
        expected[oid]=t['symbol']
    if len(expected)!=137 or any(not ids['statusByOrder'].get(k,{}).get('matched') for k in expected):
        raise PermissionError('ORDER_IDENTITIES_NOT_FULLY_RECONCILED')
    if CK.exists():ck=json.loads(CK.read_text(encoding='utf-8'))
    else:ck={'snapshotAt':source['checkedAt'],'orders':{}}
    if ck.get('snapshotAt')!=source['checkedAt']:raise ValueError('ECONOMIC_CHECKPOINT_SCOPE_CHANGED')
    # Older WEEX per-order trade queries may return an empty list while the
    # independently collected authenticated 1000-trade snapshot has its fills.
    # Re-evaluate only prior missing-fill failures; exact executedQty equality
    # is mandatory before the fallback can certify full order economics.
    for oid,old in list(ck['orders'].items()):
        if old.get('reason')=='MISSING_OR_PAGINATED_FILLS':
            del ck['orders'][oid]
    save(CK,ck)
    grouped={}
    for t in trades:grouped.setdefault(str(t['orderId']),[]).append(t)
    # Reserve capacity for live account/recovery reads. Do not call the API
    # when the shared 10-minute quota is near its safety ceiling.
    quota=budget().used()
    quota_weight=quota.get('weight')
    if type(quota_weight) not in (int,float):
        raise PermissionError('WEEX_BUDGET_TELEMETRY_UNAVAILABLE')
    quota_paused=quota_weight>=470
    processed=0;deferred=quota_paused
    for oid,symbol in sorted(expected.items()):
        if quota_paused:break
        if oid in ck['orders']:continue
        if processed>=max_orders:break
        try:
            order=query('/capi/v3/order?orderId='+oid)
            fills=grouped.get(oid,[])
            evidence_source='AUTHENTICATED_1000_TRADE_SNAPSHOT'
            proof=verify(order,fills)
            # Fall back to an exact exchange query only when the bounded
            # snapshot cannot certify all fills of this order. Never infer
            # completeness from a truncated temporal boundary.
            if not proof.get('verified'):
                fills=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
                evidence_source='EXACT_ORDER_FILL_GET'
                proof=verify(order,fills)
            ck['orders'][oid]={'verified':proof.get('verified') is True,
                 'evidenceSource':evidence_source,
                 'reason':proof.get('reason'),'fillCount':proof.get('fillCount'),
                 'notionalUSDT':proof.get('executedFillNotionalUSDT'),
                 'feesUSDT':proof.get('executionFeeUSDT'),
                 'parentQuoteDifferenceUSDT':proof.get('parentOrderQuoteDifferenceUSDT'),
                 'cumQuoteEqualFill':proof.get('parentCumQuoteEqualFillSum')}
            processed+=1
        except Exception as exc:
            if type(exc).__name__=='BudgetDeferred':
                deferred=True;break
            ck['orders'][oid]={'verified':False,'reason':'READ_FAILED',
                               'errorClass':type(exc).__name__}
            processed+=1
        save(CK,ck)
    passed=[x for x in ck['orders'].values() if x.get('verified')]
    final=len(ck['orders'])==len(expected) and len(passed)==len(expected)
    out={'checkedAt':datetime.now(timezone.utc).isoformat(),
      'snapshotAt':source['checkedAt'],'ordersIn1000TradeSnapshot':len(expected),
      'ordersAudited':len(ck['orders']),'ordersVerified':len(passed),
      'ordersFailed':len(ck['orders'])-len(passed),
      'remainingOrders':len(expected)-len(ck['orders']),
      'newAuditsThisRun':processed,'apiBudgetDeferred':deferred,
      'quotaPreflightPaused':quota_paused,'quotaWeightAtPreflight':quota_weight,
      'verifiedOrderNotionalUSDT':str(sum((D(x['notionalUSDT']) for x in passed),D(0))),
      'verifiedOrderFeesUSDT':str(sum((D(x['feesUSDT']) for x in passed),D(0))),
      'allSnapshotOrderEconomicsVerified':final,'fullHistoricalCoverage':False,
      'fundingVerified':False,'liveGateOverride':False,'exchangeWrites':False}
    save(REPORT,out)
    return out
if __name__=='__main__':print(json.dumps(run()))
