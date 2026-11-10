"""Read-only WEEX live position coverage observer; no order actions.

A TP does not substitute for an SL. Coverage is informational and never
authorizes adoption of manual positions or exchange writes.
"""
import json
from datetime import datetime,timezone
from pathlib import Path
from decimal import Decimal,InvalidOperation
from weex_capacity import full_closing_tp

def positive_decimal(value):
    try:
        v=Decimal(str(value))
        return v if v.is_finite() and v>0 else None
    except (InvalidOperation,ValueError,TypeError):
        return None

def stop_covers_position(position,algo):
    """Evidence of exact residual-size, close-side, active stop. Not a guarantee of fill."""
    if not isinstance(position,dict) or not isinstance(algo,dict):return False
    side=position.get('side')
    if side not in ('LONG','SHORT') or position.get('symbol')!=algo.get('symbol'):return False
    if algo.get('positionSide')!=side:return False
    if algo.get('side')!=('SELL' if side=='LONG' else 'BUY'):return False
    if algo.get('orderType') not in STOPS or algo.get('reduceOnly') is not True:return False
    if algo.get('algoStatus') not in ('NEW','UNTRIGGERED'):return False
    qty=positive_decimal(position.get('size'))
    ordered=positive_decimal(algo.get('quantity'))
    trigger=positive_decimal(algo.get('triggerPrice'))
    if qty is None or ordered is None or qty!=ordered or trigger is None:return False
    return True
ROOT=Path(__file__).resolve().parent
STOPS={'STOP_MARKET','STOP_LOSS','STOP_LOSS_MARKET'}
def assess(positions,orders,algos):
    if not all(isinstance(x,list) for x in (positions,orders,algos)):
        return {'status':'SNAPSHOT_INVALID','newEntriesAllowed':False,'rows':[]}
    if any(not isinstance(x,dict) for group in (positions,orders,algos) for x in group):
        return {'status':'SNAPSHOT_INVALID','newEntriesAllowed':False,'rows':[]}
    rows=[]
    for p in positions:
        symbol=p.get('symbol');side=p.get('side')
        if not symbol or side not in ('LONG','SHORT'):
            return {'status':'POSITION_IDENTITY_UNKNOWN','newEntriesAllowed':False,'rows':[]}
        match=[a for a in algos if a.get('symbol')==symbol and
               a.get('positionSide')==side]
        tp=any(full_closing_tp(a,[p]) for a in match)
        # Exact numeric residual quantity, closing direction, active
        # conditional status, reduceOnly and positive trigger are required.
        sl=any(stop_covers_position(p,a) for a in match)
        rows.append({'symbol':symbol,'side':side,'fullTpObserved':tp,
                     'fullStopObserved':sl,'botOwnershipVerified':False,
                     'canAutoRepair':False})
    return {'status':'REVIEW_REQUIRED' if any(
            not r['fullTpObserved'] or not r['fullStopObserved'] for r in rows) else
            'COVERAGE_OBSERVED_NOT_OWNERSHIP_PROOF',
            'positionCount':len(rows),'newEntriesAllowed':False,
            'unprotectedCount':sum(not r['fullStopObserved'] for r in rows),
            'withoutFullTpCount':sum(not r['fullTpObserved'] for r in rows),
            'rows':rows,'liveWrites':0}
def run():
    from weex_live_worker import Reader
    from weex_live_guardian_shadow_gate import current_state
    positions,orders,algos=Reader(ROOT).account()
    coverage=assess(positions,orders,algos)
    from weex_live_manual_attestation import classify
    manual=classify(ROOT,positions)
    from weex_live_existing_telegram_ack_shadow import assess as telegram_ack_assess
    existing_telegram_ack=telegram_ack_assess(ROOT,positions)
    from weex_live_manual_isolation_policy import assess as isolation_assess
    configuration=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    separation=isolation_assess(ROOT,positions,orders,algos,
         margin_preference=configuration.get('risk',{}).get('marginModePreference'))
    gate=current_state(ROOT,position_count=len(positions),
                       algo_count=len(algos),position_ownership=False)
    result={'checkedAt':datetime.now(timezone.utc).isoformat(),
            'source':'WEEX_LIVE_READ_ONLY','coverage':coverage,'manualPositions':manual,
            'telegramAcknowledgements':existing_telegram_ack,
            'operationalSeparation':separation,'gate':gate,
            'liveWrites':0,'liveEnabledByAudit':False}
    target=ROOT/'weex_live_guardian_shadow_latest.json'
    tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2),encoding='utf-8')
    tmp.replace(target)
    return result
if __name__=='__main__':
    try:print(json.dumps(run()))
    except Exception as e:print(json.dumps({'status':'READ_ONLY_AUDIT_FAILED',
       'errorType':type(e).__name__,'liveWrites':0}))
