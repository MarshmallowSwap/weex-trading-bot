"""Create one-shot WEEX simulator old-stop-cancel ACK-loss canary.
No live host, no repeated cancellation; GET-only reconciliation.
"""
from pathlib import Path
root=Path(__file__).resolve().parent
s=(root/'weex_sim_journaled_replacement_canary.py').read_text(encoding='utf-8')
old="""        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_OLD_STOP_CANCEL_UNCONFIRMED')"""
new="""        from weex_partial_guardian_sim_readback import guardian_confirm_pending
        from urllib.request import urlopen
        intercepted={'cancelCalls':0}
        def lose_cancel_ack_after_response(req,timeout=8):
            expected='https://api-sim.weex.com/capi/v3/algoOrder?orderId='+str(known[0])
            if req.get_method()!='DELETE' or req.full_url!=expected:
                raise ValueError('CANCEL_FAULT_SCOPE_DENIED')
            if intercepted['cancelCalls']>=1:
                raise ValueError('DUPLICATE_CANCEL_DENIED')
            intercepted['cancelCalls']+=1
            with urlopen(req,timeout=timeout) as resp:
                resp.read()
            raise TimeoutError('DEMO_CANCEL_ACK_LOST_AFTER_HTTP_RESPONSE')
        first=execute_one(ledger,trade_id,new_stop_trigger=sl,
                          new_tp_limit=tp,transport=lose_cancel_ack_after_response)
        s['cancelAckState']=first.get('state')
        s['cancelWriteCalls']=intercepted['cancelCalls']
        if first.get('state')!='ACK_UNCERTAIN' or intercepted['cancelCalls']!=1:
            raise ValueError('CANCEL_FAULT_NOT_RECOGNIZED')
        # Crucially: recover by authenticated GET; never call execute_one again.
        journal_result=guardian_confirm_pending(ledger,trade_id)
        s['cancelRecoveredViaGET']=journal_result.get('confirmedByReadback') is True
        s['journalStepStates'].append(journal_result.get('state'))
        if not s['cancelRecoveredViaGET']:
            raise ValueError('JOURNAL_OLD_STOP_CANCEL_UNCONFIRMED')"""
if s.count(old)!=1:raise ValueError('CANCEL_STEP_ANCHOR_NOT_UNIQUE')
s=s.replace(old,new)
oldstatus="s['status']='DEMO_JOURNALED_REPLACEMENT_VERIFIED' if ("
newstatus="""s['status']='DEMO_CANCEL_ACK_LOSS_RECOVERY_VERIFIED' if (
       s.get('cancelWriteCalls')==1 and s.get('cancelRecoveredViaGET') and"""
if s.count(oldstatus)!=1:raise ValueError('STATUS_ANCHOR_NOT_UNIQUE')
s=s.replace(oldstatus,newstatus)
out=root/'weex_sim_journaled_cancel_ack_loss_canary.py'
out.write_text(s,encoding='utf-8')
compile(s,str(out),'exec')
print('SIM_CANCEL_ACK_LOSS_CANARY_READY')
