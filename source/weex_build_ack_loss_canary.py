"""Build a one-shot simulator canary with an ACK-loss after WEEX confirms the write.

First Guardian replacement SL is transmitted exactly once to API-SIM.
Transport reads the authenticated HTTP body, then deliberately throws.
The durable recovery uses only fresh authenticated GET; no resend.
The established canary closes the position in finally if anything fails.
"""
from pathlib import Path
root=Path(__file__).resolve().parent
s=(root/'weex_sim_journaled_replacement_canary.py').read_text(encoding='utf-8')
old="""        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_NEW_STOP_UNCONFIRMED')"""
new="""        # Inject ACK loss AFTER exchange response read, not before the order.
        from weex_partial_guardian_sim_readback import guardian_confirm_pending
        from urllib.request import urlopen
        intercepted={'writeCalls':0}
        def deliberately_lose_first_ack(req,timeout=8):
            if req.get_method()!='POST' or not req.full_url.startswith('https://api-sim.weex.com/capi/v3/placeTpSlOrder'):
                raise ValueError('FAULT_INJECTION_SCOPE_DENIED')
            if intercepted['writeCalls']>=1:
                raise ValueError('DUPLICATE_WRITE_DENIED')
            intercepted['writeCalls']+=1
            with urlopen(req,timeout=timeout) as response:
                response.read()
            raise TimeoutError('DEMO_ACK_LOST_AFTER_EXCHANGE_RESPONSE')
        first=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp,
                          transport=deliberately_lose_first_ack)
        s['injectedAckState']=first.get('state')
        s['injectedFirstWriteCount']=intercepted['writeCalls']
        if first.get('state')!='ACK_UNCERTAIN' or intercepted['writeCalls']!=1:
            raise ValueError('INJECTION_NOT_RECOGNIZED')
        # Never call execute_one a second time. The next operation is GET-only.
        journal_result=guardian_confirm_pending(ledger,trade_id)
        s['ackRecoveredViaGET']=journal_result.get('confirmedByReadback') is True
        s['journalStepStates'].append(journal_result.get('state'))
        if not s['ackRecoveredViaGET']:
            raise ValueError('JOURNAL_NEW_STOP_UNCONFIRMED')"""
if s.count(old)!=1:raise ValueError('ACK_INJECTION_HOOK_MISSING')
s=s.replace(old,new)
s=s.replace("s['status']='DEMO_JOURNALED_REPLACEMENT_VERIFIED' if (",
            "s['status']='DEMO_ACK_LOSS_RECOVERY_VERIFIED' if (\n       s.get('injectedFirstWriteCount')==1 and s.get('ackRecoveredViaGET') and")
target=root/'weex_sim_journaled_ack_loss_canary.py'
target.write_text(s,encoding='utf-8')
compile(s,str(target),'exec')
print('ACK_LOSS_CANARY_READY')
