"""Independent ETHUSDT Isolated 1x *preparation* gate, no live orders.

Unlike the full production release gate, this can independently evaluate pilot
readiness without demanding production's live-crash proof. Execution is never
authorized here: only a separately attested emergency close and real lifecycle
may qualify a subsequent controlled transport.
"""
from decimal import Decimal, InvalidOperation

def assess(pilot, observed, journal, *, main_switch, integrity_errors):
    issues=[]
    if main_switch!='STOPPED':issues.append('MAIN_BOT_NOT_STOPPED')
    if integrity_errors:issues.append('CODE_INTEGRITY_FAILED')
    if not isinstance(pilot,dict) or not isinstance(observed,dict):
        return {'pilotPreparationReady':False,'pilotOrderAuthorized':False,
                'exchangeWrites':0,'issues':['INVALID_INPUT']}
    if (pilot.get('exchange')!='WEEX' or pilot.get('marginMode')!='ISOLATED'
        or pilot.get('leverage')!=1 or pilot.get('maxNewOrders')!=1
        or pilot.get('executionEnabled') is not False
        or pilot.get('liveOrderSubmissionAllowed') is not False):
        issues.append('INVALID_ISOLATED_PILOT_SCOPE')
    if journal.get('state')!='READ_ONLY' or journal.get('records')!=0 or journal.get('dispatchRows')!=0:
        issues.append('PILOT_JOURNAL_NOT_PRISTINE')
    # Exchange evidence from upstream GET-only audit. Drop ONLY the global
    # production certification prerequisites that cannot precede a real pilot.
    inherited=set(observed.get('issues',[]))
    # The preparation gate must not require the *result* of the future real
    # pilot. A separate execution gate must still require a tested exit.
    deferred={'INDEPENDENT_GATE_NO_GO','LIVE_CRASH_RESTART_NOT_CERTIFIED',
              'REDUCE_ONLY_EXIT_NOT_VERIFIED'}
    # Pilot policy says optional SL; explicit risk warning remains.
    if pilot.get('stopLossVerified') is not True:
        inherited.discard('PILOT_STOP_LOSS_NOT_VERIFIED')
    unresolved=inherited-deferred
    issues.extend(sorted(unresolved))
    try:
        size=observed['indicativeOrder']
        quantity=Decimal(str(size['quantity']))
        notional=Decimal(str(size['notionalUSDT']))
        step=Decimal(str(size['quantityStep']))
        if not all(v.is_finite() and v>0 for v in (quantity,notional,step)):
            raise ValueError('INVALID_NUMBERS')
        if notional>Decimal('5') or quantity%step!=0:
            raise ValueError('OUT_OF_SCOPE')
    except (KeyError,InvalidOperation,ValueError,TypeError,AttributeError):
        issues.append('PILOT_ORDER_SIZE_NOT_CERTIFIED')
    # Preparation does not grant real-money permission. The independent
    # execution requirements remain visible, including an unverified close.
    close_verified=pilot.get('reduceOnlyCloseVerified') is True
    live_blockers=[] if close_verified else ['EMERGENCY_CLOSE_NOT_ATTESTED','REDUCE_ONLY_EXIT_NOT_VERIFIED']
    return {'pilotPreparationReady':not issues,'pilotOrderAuthorized':False,
            'pilotLiveExecutionReady':False,'liveExecutionBlockers':live_blockers,
            'pilotIndependentFromProductionGate':True,'mainProductionGateBypassed':False,
            'mainSwitchRequired':'STOPPED','exchangeWrites':0,
            'warnings':['ISOLATED_POSITION_MAY_LOSE_UP_TO_MARGIN_WITHOUT_STOP'],
            'issues':sorted(set(issues))}
