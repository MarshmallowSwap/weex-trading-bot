"""Single entrypoint for WEEX isolated 1x pilot monitoring and readiness.

Authenticated GET observations only. Does not reserve a new order, grant
permissions, touch leverage/margin, or call a write-capable transport.
"""
import json,os
from datetime import datetime,timezone
from pathlib import Path
from weex_pilot_dispatch_readback_run import run as recover
from weex_pilot_independent_readonly_run import run as preflight
from weex_pilot_unified_lifecycle_readonly import run as lifecycle
from weex_pilot_emergency_close_readonly import run as close_observation
from weex_pilot_emergency_attested_readonly_run import run as emergency_attestation
from weex_existing_account_1x_pilot_audit import journal_inventory
from weex_pilot_live_entry_coordinator import prepare_entry
from weex_pilot_live_close_coordinator import emergency_close_owned
import live_control

ROOT=Path(__file__).resolve().parent

def decide(*,config,preparation,recovery,journal,production_mode,integrity):
    issues=[]
    if production_mode!='STOPPED':issues.append('MAIN_STRATEGY_MUST_REMAIN_STOPPED')
    if integrity:issues.append('INTEGRITY_CHECK_FAILED')
    if not preparation.get('pilotPreparationReady'):issues.append('PILOT_PREPARATION_NOT_READY')
    if journal.get('records',0)>1:issues.append('MORE_THAN_ONE_PILOT')
    if recovery.get('pendingFound',0)>0:issues.append('PENDING_ORDER_READBACK_MUST_BE_RESOLVED')
    # Stop-loss is optional in this isolated 1x pilot policy. Lack of one
    # remains a risk warning; it must not masquerade as a hard software fault.
    for key in ('executionEnabled','liveOrderSubmissionAllowed','reduceOnlyCloseVerified'):
        if config.get(key) is not True:issues.append(key.upper()+'_NOT_VERIFIED')
    if config.get('maxNewOrders')!=1 or config.get('leverage')!=1 or config.get('marginMode')!='ISOLATED':
        issues.append('PILOT_SCOPE_MISMATCH')
    return {'phase':'PREFLIGHT_ONLY','readOnly':True,'entryAuthorized':False,
            'closeAuthorized':False,'liveReady':False,'blockingReasons':issues,
            'riskWarnings':([] if config.get('stopLossVerified') is True
                            else ['NO_VERIFIED_STOP_LOSS_ISOLATED_MARGIN_AT_RISK']),
            'nextRequiredAction':('VERIFY_EXCHANGE_EXIT_AND_ORDER_PERMISSION' if issues
                                  else 'MANUAL_EXECUTION_REVIEW_STILL_REQUIRED')}

def run(root=ROOT):
    root=Path(root)
    state=live_control.state(root)
    if state['mode']!='STOPPED':raise PermissionError('MAIN_BOT_NOT_STOPPED')
    integrity=live_control.build_errors(root)
    if integrity:raise PermissionError('PRODUCTION_INTEGRITY_FAILED')
    config=json.loads((root/'weex_live_1x_pilot_config.json').read_text())
    # Read any unknown dispatch first; never auto-retry.
    recovery=recover(root)
    preparation=preflight()
    lifecycle_result=lifecycle()
    close_result=close_observation()
    emergency_result=emergency_attestation(root)
    journal=journal_inventory(root/'weex_isolated_pilot.sqlite3')
    result=decide(config=config,preparation=preparation,recovery=recovery,
                  journal=journal,production_mode=state['mode'],integrity=integrity)
    result.update({'checkedAt':datetime.now(timezone.utc).isoformat(),
                   'recovery':{'pendingFound':recovery['pendingFound'],'results':recovery['results']},
                   'preparationReady':preparation['pilotPreparationReady'],
                   'journal':journal,'lifecycle':lifecycle_result,
                   'closureObservations':close_result,
                   'emergencyOwnershipReadback':emergency_result,
                   'realOrdersSubmitted':0,'mainStrategyMode':state['mode']})
    outfile=root/'weex_pilot_orchestrator_latest.json'
    temporary=outfile.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temporary,outfile)
    return result

if __name__=='__main__':
    import sys
    if len(sys.argv)>1:
        if sys.argv[1] not in ('--pilot-entry','--pilot-close'):
            raise SystemExit('SUPPORTED: --pilot-entry|--pilot-close <pilot-id>')
        if len(sys.argv)!=3:raise SystemExit('REQUIRED: action <pilot-id>')
        # CLI never manufactures an order or position approval.
        if sys.argv[1]=='--pilot-entry':
            prepare_entry(ROOT,pilot_id=sys.argv[2],authorization=None)
        else:
            emergency_close_owned(ROOT,pilot_id=sys.argv[2],approve=None)
        raise SystemExit('NOT_AUTHORIZED')
    r=run()
    print(json.dumps({k:r[k] for k in ('checkedAt','phase','preparationReady','blockingReasons',
        'nextRequiredAction','realOrdersSubmitted','mainStrategyMode')},ensure_ascii=False))
