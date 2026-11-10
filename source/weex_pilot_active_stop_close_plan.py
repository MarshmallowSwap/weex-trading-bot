"""GET-evidence-only plan for exact-position close with active attached stop.

Does not cancel the stop or send an order. Requires flat prior baseline,
journaled protected entry, independently authenticated parent/fills/position,
and exactly one exchange-side stop linked to that same parent.
"""
import json
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_ownership_attestation import attest
from weex_pilot_attached_stop_evidence import protected_entry
from weex_pilot_emergency_close_sdk import exact_payload
from weex_pilot_exit_stop_lifecycle import assess as lifecycle

def assess(db,pilot_id,*,baseline,positions,regular_orders,conditional_orders,
           entry_order,entry_fills):
    deny=lambda reason:{'prepared':False,'canSend':False,'reason':reason,
                        'stopCancellationRequired':False,'exchangeWrites':0}
    if not all(isinstance(x,list) for x in (positions,regular_orders,
                                            conditional_orders,entry_fills)):
        return deny('EXCHANGE_DATA_INCOMPLETE')
    if len(positions)!=1 or regular_orders or len(conditional_orders)!=1:
        return deny('POSITION_STOP_NOT_EXCLUSIVE')
    with closing(connect(db)) as c:
        row=c.execute('SELECT side,quantity,state,entry_id,proposals FROM pilot_v1 WHERE pilot_id=?',
                      (pilot_id,)).fetchone()
        if row is None:return deny('UNKNOWN_PILOT')
        side,quantity,state,cid,raw=row
        if state!='ENTRY_RECONCILED_EXTERNALLY':return deny('ENTRY_NOT_RECONCILED')
        tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('pilot_emergency_dispatch_v1','pilot_close_dispatch_v1','pilot_exit_mutex_v1'):
            if table in tables and c.execute('SELECT 1 FROM '+table+' WHERE pilot_id=?',(pilot_id,)).fetchone():
                return deny('EXIT_ALREADY_RESERVED_OR_UNKNOWN')
        try:proposals=json.loads(raw)
        except (TypeError,ValueError):return deny('JOURNAL_PROPOSAL_INVALID')
    ownership=attest(baseline=baseline,position=positions[0],entry=entry_order,
                     fill_rows=entry_fills,pilot={'side':side,'quantity':quantity,
                                                 'entryId':cid})
    if ownership.get('owned') is not True:
        return deny('OWNERSHIP_NOT_ATTESTED:'+ownership.get('reason','UNKNOWN'))
    stop=protected_entry(proposals,entry_order,conditional_orders,side,quantity)
    if stop.get('verified') is not True:
        return deny('ATTACHED_STOP_NOT_ATTESTED:'+stop.get('reason','UNKNOWN'))
    lifecycle_proof=lifecycle(positions=positions,regular=regular_orders,
        conditional=conditional_orders,expected_position=positions[0],
        expected_stop={'algoId':stop['algoId'],'triggerPrice':stop['triggerPrice']})
    if (lifecycle_proof.get('reason')!='STOP_ACTIVE_CANCEL_CONFIRMATION_REQUIRED_BEFORE_POSITION_CLOSE'
        or str(lifecycle_proof.get('positionId'))!=ownership['positionId']):
        return deny('STOP_LIFECYCLE_NOT_EXACT')
    try:payload=exact_payload(ownership['positionId'])
    except (ValueError,TypeError,KeyError):return deny('POSITION_ID_INVALID')
    return {'prepared':True,'canSend':False,'reason':'ACTIVE_STOP_EXACT_CLOSE_PREPARED',
            'payload':payload,'attestation':ownership,
            'attachedStopAlgoId':stop['algoId'],'stopCancellationRequired':False,
            'requiresFreshExchangeReadback':True,'requiresExplicitPositionApproval':True,
            'postCloseProofRequired':('EXACT_REDUCE_ONLY_FILL','ACCOUNT_FLAT',
                                     'NO_RESIDUAL_CONDITIONAL'),
            'exchangeWrites':0}
