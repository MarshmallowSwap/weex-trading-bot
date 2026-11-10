"""Pilot position-specific live exit coordinator, using exchange GET ownership.

Does not authorize account-wide close, never uses a user-supplied 'owned' flag,
and never retries an unknown exchange outcome. Requires independent exact
operator approval; the CLI supplies none by default.
"""
import json
from pathlib import Path
from weex_live_worker import Reader
from weex_order_pagination import history
from monitor import query
from weex_pilot_unified_lifecycle_readonly import journals
from weex_pilot_baseline_load import load as baseline_load
from weex_pilot_emergency_attested_plan import assess
from weex_pilot_active_stop_close_plan import assess as assess_active_stop_close
from weex_pilot_emergency_dispatch import dispatch
from weex_pilot_emergency_close_sdk import PilotEmergencyCloseSDK
from weex_pilot_exit_stop_lifecycle import assess as exit_stop_assess
import live_control

ROOT=Path(__file__).resolve().parent

def emergency_close_owned(root=ROOT,*,pilot_id,approve=None):
    root=Path(root)
    if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
        raise PermissionError('PRODUCTION_NOT_STOPPED_OR_INTEGRITY_FAILED')
    cfg=json.loads((root/'weex_live_1x_pilot_config.json').read_text())
    if cfg.get('executionEnabled') is not True or cfg.get('liveOrderSubmissionAllowed') is not True:
        raise PermissionError('PILOT_EXECUTION_NOT_ENABLED')
    if approve is None:raise PermissionError('EXACT_POSITION_APPROVAL_REQUIRED')
    db=root/'weex_isolated_pilot.sqlite3'
    pilots=[x for x in journals(db) if x['pilotId']==pilot_id]
    if len(pilots)!=1:raise PermissionError('PILOT_ID_NOT_UNIQUE')
    pilot=pilots[0]
    baseline=baseline_load(root/'weex_pilot_flat_baseline_latest.json',max_age_ms=3600000)
    if baseline is None:raise PermissionError('FLAT_BASELINE_INVALID_OR_EXPIRED')
    positions,regular,conditional=Reader(root).account()
    if not all(isinstance(x,list) for x in (positions,regular,conditional)):
        raise PermissionError('EXCHANGE_ACCOUNT_READ_INCOMPLETE')
    if len(positions)!=1 or regular:
        raise PermissionError('NONEXCLUSIVE_EXCHANGE_POSITION_OR_OPEN_ORDERS')
    # The active-stop pathway requires exact parent/child/baseline evidence.
    # Do not cancel the exchange stop before closing. Other stop states fail
    # closed after the entry and exit evidence has been independently read.
    hist=history(max_pages=5)
    if hist.get('completeWithinRequestedBounds') is not True:
        raise PermissionError('HISTORY_PAGINATION_NOT_COMPLETE')
    candidates=[x for x in hist['orders'] if x.get('clientOrderId')==pilot['entryId']]
    if len(candidates)!=1:raise PermissionError('PILOT_ENTRY_NOT_UNIQUE')
    oid=str(candidates[0].get('orderId') or '')
    if not oid:raise PermissionError('ENTRY_EXCHANGE_ORDER_ID_MISSING')
    order=query('/capi/v3/order?orderId='+oid)
    if not isinstance(order,dict) or str(order.get('orderId'))!=oid or order.get('clientOrderId')!=pilot['entryId']:
        raise PermissionError('EXACT_ENTRY_READBACK_MISMATCH')
    fills=query('/capi/v3/userTrades?symbol=ETHUSDT&orderId='+oid+'&limit=100')
    if not isinstance(fills,list) or not fills or len(fills)>=100:
        raise PermissionError('ENTRY_FILLS_INCOMPLETE')
    if conditional:
        plan=assess_active_stop_close(db,pilot_id,baseline=baseline,
            positions=positions,regular_orders=regular,conditional_orders=conditional,
            entry_order=order,entry_fills=fills)
    else:
        stop_gate=exit_stop_assess(positions=positions,regular=regular,
            conditional=conditional,expected_position=positions[0])
        if stop_gate.get('readyToDispatchEmergency') is not True:
            raise PermissionError('EXIT_STOP_LIFECYCLE_BLOCKED:'+stop_gate['reason'])
        plan=assess(db,pilot_id,baseline=baseline,positions=positions,
            regular_orders=regular,conditional_orders=conditional,
            entry_order=order,entry_fills=fills)
    if plan.get('prepared') is not True:
        raise PermissionError('EXIT_NOT_ATTESTED:'+plan.get('reason','UNKNOWN'))
    payload=plan['payload']
    if approve({'pilotId':pilot_id,'symbol':payload['symbol'],
                'positionId':payload['positionId'],'side':pilot['side'],
                'quantity':pilot['quantity']}) is not True:
        raise PermissionError('EXACT_POSITION_APPROVAL_DENIED')
    adapter=PilotEmergencyCloseSDK(root,authorization=lambda op,p:
                                   approve({'pilotId':pilot_id,'symbol':p['symbol'],
                                   'positionId':p['positionId'],'side':pilot['side'],
                                   'quantity':pilot['quantity']}) is True)
    return dispatch(db,pilot_id,ownership=plan['attestation'],
                    observed_position=positions[0],transport=adapter,main_mode='STOPPED')
