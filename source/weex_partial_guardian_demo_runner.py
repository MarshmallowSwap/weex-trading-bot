"""Simulation-only Guardian runner with injectable, NO-NETWORK transport.

All operations are delegated to a deliberately memory-only fake exchange.
This module imports no WEEX credential or HTTP library; production dispatch
is impossible. Before a simulated write, durable note_attempt is committed.
After crash/timeout the caller must explicitly invoke recover(), which only
reads and validates the exchange snapshot. No blind resend.
"""
import hashlib,json
from weex_partial_guardian_persistent import (evaluate,note_attempt,confirm_step,
                                               STEPS,canonical)
from weex_partial_exit_replace_guard import inspect

class FaultInjected(Exception):pass

class MemoryOnlyDemo:
    def __init__(self,positions,algos,regular_orders=None):
        self.positions=[dict(x) for x in positions]
        self.algos=[dict(x) for x in algos]
        self.regular_orders=list(regular_orders or [])
        self.writes=0
        self.calls=[]
        self.fail_read=False
        self.fail_before_write=False
        self.fail_after_write=False
    def snapshot(self):
        if self.fail_read:raise FaultInjected('READ_INTERRUPTED')
        return {'positions':[dict(x) for x in self.positions],
                'algos':[dict(x) for x in self.algos],
                'regular_orders':[dict(x) for x in self.regular_orders]}
    def apply(self,step,details):
        if self.fail_before_write:raise FaultInjected('BEFORE_SEND')
        self.calls.append(step);self.writes+=1
        oid=details['old_id'];nsl=details['new_sl'];ntp=details['new_tp']
        if step==STEPS[0]:
            self.algos.append(dict(nsl))
        elif step==STEPS[1]:
            self.algos=[x for x in self.algos if x.get('algoId')!=oid['sl']]
        elif step==STEPS[2]:
            self.algos=[x for x in self.algos if x.get('algoId')!=oid['tp']]
        elif step==STEPS[3]:
            self.algos.append(dict(ntp))
        else:raise ValueError('UNKNOWN_STEP')
        if self.fail_after_write:raise FaultInjected('AFTER_SEND_BEFORE_ACK')
        return {'memoryOnly':True,'writeApplied':True}

def fingerprint(step,details):
    return hashlib.sha256(canonical({'step':step,'details':details}).encode()).hexdigest()

def _read(ex):
    s=ex.snapshot()
    if not isinstance(s,dict) or set(s)!=set(('positions','algos','regular_orders')):
        raise ValueError('INCOMPLETE_DEMO_SNAPSHOT')
    return s

def start_step(path,tid,ex,details,*,sim_only=True):
    if sim_only is not True or type(ex) is not MemoryOnlyDemo:
        raise PermissionError('MEMORY_ONLY_TRANSPORT_REQUIRED')
    s=_read(ex)
    observed=evaluate(path,tid,**s,authenticated_sim_readback=True)
    step=observed.get('nextInstruction')
    if step not in STEPS:
        return {'state':observed.get('state'),'reason':observed.get('reason'),
                'writesApplied':0,'canRetry':False}
    sig=fingerprint(step,details)
    note_attempt(path,tid,step=step,request_fingerprint=sig)
    try:
        result=ex.apply(step,details)
    except FaultInjected as exc:
        return {'state':'ACK_UNCERTAIN','reason':str(exc),'fingerprint':sig,
                'step':step,'canRetry':False}
    after=_read(ex)
    out=confirm_step(path,tid,step=step,request_fingerprint=sig,
                     **after,authenticated_sim_readback=True)
    return {**out,'memoryOnly':True,'step':step,'fingerprint':sig}

def recover(path,tid,ex,*,step,details):
    """Only GET-equivalent readback; never calls apply(), even on failure."""
    if type(ex) is not MemoryOnlyDemo:raise PermissionError('MEMORY_ONLY_TRANSPORT_REQUIRED')
    s=_read(ex)
    return confirm_step(path,tid,step=step,request_fingerprint=fingerprint(step,details),
                        **s,authenticated_sim_readback=True)
