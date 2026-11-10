"""Build one-shot real SIM canary with durable Guardian around each TP/SL replacement.
Initial/partial entries and final close remain the previously-tested demo canary.
No live host, no repeated order POST. Old scripts remain unchanged.
"""
from pathlib import Path
root=Path(__file__).resolve().parent
src=(root/'weex_sim_partial_replace_canary.py').read_text(encoding='utf-8')
anchor="        # Order replacement: new SL first, NEVER remove old SL before GET proof."
registration="""        # Durable journal registration after exact partial-position readback.
        from weex_partial_guardian_persistent import register
        from weex_partial_guardian_sim_executor import execute_one
        ledger=str((__import__('pathlib').Path(__file__).resolve().parent/
                    'weex_partial_guardian_demo_active.sqlite3'))
        trade_id='wxsim-journal-'+suffix
        register(ledger,trade_id,position_id=posid,symbol=SYMBOL,side='LONG',
                 old_tp_client='wxsimp'+suffix,old_sl_client='wxsimsl'+suffix,
                 new_tp_client='wxsimpnew'+suffix,new_sl_client='wxsimslnew'+suffix)
        s['journalTradeRegistered']=True
        s['journalStepStates']=[]
"""
assert src.count(anchor)==1
src=src.replace(anchor,registration+anchor)
old="        sl_http,sl_ack=call(c,'POST',TP,sl_new)"
new="""        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_NEW_STOP_UNCONFIRMED')
        sl_http=200
        new_entries=[a for a in snapshot(c)[ALGOS] if a.get('clientAlgoId')==newsid]
        sl_ack=([{'success':True,'orderId':new_entries[0]['algoId']}]
                if len(new_entries)==1 else [])"""
assert src.count(old)==1
src=src.replace(old,new)
old="        oldcancel_http,oldcancel_ack=call(c,'DELETE',CANCEL+'?orderId='+str(known[0]))"
new="""        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_OLD_STOP_CANCEL_UNCONFIRMED')
        oldcancel_http,oldcancel_ack=200,[]"""
assert src.count(old)==1
src=src.replace(old,new)
old="        tp_cancel_http,tp_cancel_ack=call(c,'DELETE',CANCEL+'?orderId='+str(known[1]))"
new="""        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_OLD_TP_CANCEL_UNCONFIRMED')
        tp_cancel_http,tp_cancel_ack=200,[]"""
assert src.count(old)==1
src=src.replace(old,new)
old="        nt_http,nt_ack=call(c,'POST',TP,tp_new)"
new="""        journal_result=execute_one(ledger,trade_id,new_stop_trigger=sl,new_tp_limit=tp)
        s['journalStepStates'].append(journal_result.get('state'))
        if not journal_result.get('confirmedByReadback'):
            raise ValueError('JOURNAL_NEW_TP_UNCONFIRMED')
        nt_http=200
        new_entries=[a for a in snapshot(c)[ALGOS] if a.get('clientAlgoId')==newtpid]
        nt_ack=([{'success':True,'orderId':new_entries[0]['algoId']}]
                if len(new_entries)==1 else [])"""
assert src.count(old)==1
src=src.replace(old,new)
src=src.replace("s['status']='DEMO_REPLACEMENT_AND_CLEANUP_VERIFIED' if (",
"""s['status']='DEMO_JOURNALED_REPLACEMENT_VERIFIED' if (
       s.get('journalStepStates')==['DUPLICATE_STOPS_REVIEW',
       'NEW_STOP_ONLY_OLD_TP_REVIEW','NEW_STOP_PRESENT_TP_MISSING',
       'PAIR_RESTORED_OFFLINE_ONLY'] and""")
if 'DEMO_JOURNALED_REPLACEMENT_VERIFIED' not in src:raise ValueError('FINAL_GATE_MISSING')
dest=root/'weex_sim_journaled_replacement_canary.py'
dest.write_text(src,encoding='utf-8')
compile(src,str(dest),'exec')
print('JOURNALED_SIM_CANARY_BUILT')
