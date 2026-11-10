"""Build an isolated replacement demo canary from known partial test.
Keeps original script unchanged and forces a readback at every destructive step.
"""
from pathlib import Path
root=Path(__file__).resolve().parent
original=(root/'weex_sim_partial_close_canary.py').read_text(encoding='utf-8')
replacement=original.replace("body.get('quantity')!=Q or body.get('planType')", "body.get('quantity') not in (Q,HALF) or body.get('planType')")
if replacement==original:raise ValueError('SCOPE_GUARD_NOT_PATCHED')
needle="        if not s['partialObserved']:raise ValueError('PARTIAL_CLOSE_NOT_VERIFIED')"
if replacement.count(needle)!=1:raise ValueError('CANARY_ANCHOR_NOT_UNIQUE')
new_code="""        if not s['partialObserved']:raise ValueError('PARTIAL_CLOSE_NOT_VERIFIED')
        # Order replacement: new SL first, NEVER remove old SL before GET proof.
        newsid='wxsimslnew'+suffix
        sl_new={'symbol':SYMBOL,'clientAlgoId':newsid,
                'planType':'STOP_LOSS','triggerPrice':sl,'executePrice':'0',
                'quantity':HALF,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
        s['newStopPostAttempted']=True
        sl_http,sl_ack=call(c,'POST',TP,sl_new)
        s['newStopHttpStatus']=sl_http
        if sl_http!=200 or not isinstance(sl_ack,list) or len(sl_ack)!=1 or sl_ack[0].get('success') is not True:
            raise ValueError('NEW_STOP_REJECTED_OLD_STOP_RETAINED')
        newid=sl_ack[0].get('orderId')
        if not isinstance(newid,int):raise ValueError('NEW_STOP_ORDER_ID_MISSING')
        known.append(newid)
        snap=snapshot(c)
        active=snap[ALGOS]
        newstop=[a for a in active if str(a.get('algoId',a.get('orderId')))==str(newid)
                  and Decimal(str(a.get('quantity')))==Decimal(HALF)]
        oldstop=[a for a in active if str(a.get('algoId',a.get('orderId')))==str(known[0])]
        if len(newstop)!=1 or len(oldstop)!=1:
            raise ValueError('NEW_AND_OLD_STOP_NOT_SIMULTANEOUSLY_VERIFIED')
        s['newStopVerifiedBeforeCancel']=True
        # Cancel exact old SL and read back new stop before touching old TP.
        s['oldStopCancelAttempted']=True
        oldcancel_http,oldcancel_ack=call(c,'DELETE',CANCEL+'?orderId='+str(known[0]))
        s['oldStopCancelHttpStatus']=oldcancel_http
        active=snapshot(c)[ALGOS]
        if (any(str(a.get('algoId',a.get('orderId')))==str(known[0]) for a in active)
             or not any(str(a.get('algoId',a.get('orderId')))==str(newid) for a in active)):
            raise ValueError('NEW_STOP_NOT_RETAINED_AFTER_OLD_CANCEL')
        s['oldStopRemovedNewStopActive']=True
        # Original TP is now oversized. Cancel exact id and readback.
        s['oldTpCancelAttempted']=True
        tp_cancel_http,tp_cancel_ack=call(c,'DELETE',CANCEL+'?orderId='+str(known[1]))
        s['oldTpCancelHttpStatus']=tp_cancel_http
        active=snapshot(c)[ALGOS]
        if (any(str(a.get('algoId',a.get('orderId')))==str(known[1]) for a in active)
             or not any(str(a.get('algoId',a.get('orderId')))==str(newid) for a in active)):
            raise ValueError('OLD_TP_CANCEL_OR_NEW_STOP_READBACK_FAILED')
        # Place replacement TP for HALF, with original STOP still protected.
        newtpid='wxsimpnew'+suffix
        tp_new={'symbol':SYMBOL,'clientAlgoId':newtpid,
                'planType':'TAKE_PROFIT','triggerPrice':tp,'executePrice':tp,
                'quantity':HALF,'positionSide':'LONG','triggerPriceType':'CONTRACT_PRICE'}
        s['newTpPostAttempted']=True
        nt_http,nt_ack=call(c,'POST',TP,tp_new)
        s['newTpHttpStatus']=nt_http
        if nt_http!=200 or not isinstance(nt_ack,list) or len(nt_ack)!=1 or nt_ack[0].get('success') is not True:
            raise ValueError('NEW_TP_NOT_ACCEPTED')
        tpid=nt_ack[0].get('orderId')
        if not isinstance(tpid,int):raise ValueError('NEW_TP_ID_MISSING')
        known.append(tpid)
        current=snapshot(c)
        remaining=[p for p in current[POSITION] if str(p.get('id'))==str(posid)]
        active=[a for a in current[ALGOS] if str(a.get('algoId',a.get('orderId'))) in (str(newid),str(tpid))]
        s['replacementVerified']=(
            len(remaining)==1 and Decimal(str(remaining[0].get('size')))==Decimal(HALF)
            and len(active)==2
            and all(Decimal(str(a.get('quantity')))==Decimal(HALF) for a in active)
            and not current[REGULAR])
        if not s['replacementVerified']:
            raise ValueError('REPLACEMENT_PAIR_READBACK_FAILED')
"""
replacement=replacement.replace(needle,new_code)
replacement=replacement.replace("s['status']='DEMO_PARTIAL_AND_CLEANUP_VERIFIED' if (", "s['status']='DEMO_REPLACEMENT_AND_CLEANUP_VERIFIED' if (\n       s.get('replacementVerified') and")
if 's.get(\'replacementVerified\')' not in replacement:raise ValueError('RESULT_GATE_NOT_PATCHED')
dest=root/'weex_sim_partial_replace_canary.py'
dest.write_text(replacement,encoding='utf-8')
compile(replacement,str(dest),'exec')
print('DEMO_REPLACEMENT_CANARY_CREATED_VALID')
