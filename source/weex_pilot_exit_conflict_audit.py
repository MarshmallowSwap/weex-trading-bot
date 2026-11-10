"""Pilot-only exit path conflict assessment, read-only and fail-closed.

Checks known necessary conditions. A successful SDK serialization is not an
exchange acceptance or authorization. This tool never sends an order.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from weex_pilot_emergency_close_sdk import preview_position_close,exact_payload
from weex_http_guard import sdk_types,prepare_sdk_request
from weex_pilot_attached_stop_evidence import protected_entry
import live_control
ROOT=Path(__file__).resolve().parent

def assess(root=ROOT):
    root=Path(root)
    cfg=json.loads((root/'weex_live_1x_pilot_config.json').read_text())
    gate=live_control.state(root)
    errors=live_control.build_errors(root)
    _,_,ops=sdk_types()
    close_spec_ok=(ops['post_capi_v3_closePositions']['method']=='POST' and
                   ops['post_capi_v3_closePositions']['path']=='/capi/v3/closePositions')
    close_preview_ok=False
    if close_spec_ok:
        try:close_preview_ok=preview_position_close(exact_payload(123456789)) is True
        except Exception:pass
    # The actual entry proposal contains a MARK_PRICE stop, yet current
    # emergency_close_owned and assess() reject any conditionalOrders.
    from weex_pilot_emergency_attested_plan import assess as plan
    import inspect
    source=inspect.getsource(plan)
    coordinator_source=inspect.getsource(__import__('weex_pilot_live_close_coordinator').emergency_close_owned)
    # The emergency coordinator now delegates to the fail-closed stop classifier.
    from weex_pilot_exit_stop_lifecycle import assess as stop_lifecycle
    synthetic_position={'symbol':'ETHUSDT','id':'123','side':'LONG',
                        'size':'0.002','marginType':'ISOLATED'}
    synthetic_stop={'symbol':'ETHUSDT','algoId':'teststop','positionSide':'LONG',
        'side':'SELL','orderType':'STOP_MARKET','algoStatus':'UNTRIGGERED',
        'reduceOnly':True,'closePosition':True,'quantity':'0','triggerPrice':'2100'}
    stop_result=stop_lifecycle(positions=[synthetic_position],regular=[],
        conditional=[synthetic_stop],expected_position=synthetic_position,
        expected_stop={'algoId':'teststop','triggerPrice':'2100'})
    blocks_with_stop=('exit_stop_assess(' in coordinator_source
                      and stop_result.get('readyToDispatchEmergency') is False)
    # Exchange readback proof requires specific conditional order attributes.
    # Until a real linked STOP is observed, this remains unverified.
    protected_stop_exchange_verified=False
    stale_stop_cleanup_verified=False
    auth_flags={k:cfg.get(k) is True for k in (
        'executionEnabled','liveOrderSubmissionAllowed','stopLossVerified','reduceOnlyCloseVerified')}
    blockers=[]
    if gate.get('mode')!='STOPPED' or errors:blockers.append('PRODUCTION_OR_INTEGRITY_NOT_SAFE')
    if not close_preview_ok:blockers.append('POSITION_CLOSE_SDK_SERIALIZATION_NOT_VERIFIED')
    if blocks_with_stop:blockers.append('EMERGENCY_CLOSE_BLOCKED_BY_ACTIVE_PROTECTIVE_STOP')
    if not protected_stop_exchange_verified:blockers.append('ATTACHED_STOP_EXCHANGE_READBACK_UNVERIFIED')
    if not stale_stop_cleanup_verified:blockers.append('AFTER_CLOSE_CONDITIONAL_CLEANUP_UNVERIFIED')
    if not all(auth_flags.values()):blockers.append('LIVE_AUTHORIZATION_FLAGS_DISABLED')
    return {'checkedAt':datetime.now(timezone.utc).isoformat(),
        'mainMode':gate.get('mode'),'buildIntegrityErrors':errors,
        'sdkPositionCloseSerializationVerified':close_preview_ok,
        'emergencyCloseRejectedWhileAttachedStopActive':blocks_with_stop,
        'attachedStopExchangeReadbackVerified':protected_stop_exchange_verified,
        'afterCloseStopCleanupVerified':stale_stop_cleanup_verified,
        'pilotFlags':auth_flags,'blockingReasons':blockers,
        'pilotReadyForRealEntry':not blockers,'exchangeWrites':0,
        'accountOrdersPlaced':0,'scope':'STATIC_AND_OFFLINE_SDK_CHECK_ONLY'}

def run():
    result=assess()
    path=ROOT/'weex_pilot_exit_conflict_audit_latest.json'
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(result,indent=2),encoding='utf-8')
    os.replace(temp,path)
    return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
