"""WEEX V3 demo-only journaled partial TP/SL step executor.

Single-step operation. Performs authenticated readback, immutable journal
record before the write, one demo request max, then independent readback.
If ANY outcome is uncertain, do not retry. The caller can recover using
guardian_confirm_pending after examining the exchange's current state.
Live transport is not supported by this module.
"""
import hashlib,json
from decimal import Decimal
from contextlib import closing
from weex_partial_guardian_persistent import (dbopen,evaluate,note_attempt,
    confirm_step,STEPS,canonical)
from weex_partial_guardian_sim_readback import snapshot,guardian_confirm_pending
from weex_partial_guardian_sim_transport import prepare,send_sim_only,UncertainWrite,UnsafeWrite

def _owned(row,client_id,expected_qty=None):
    matches=[a for a in row if a.get('clientAlgoId')==client_id]
    if len(matches)!=1:raise ValueError('ALGO_ID_NOT_UNIQUE_OR_MISSING')
    found=matches[0]
    if expected_qty is not None and Decimal(str(found.get('quantity'))) != Decimal(str(expected_qty)):
        raise ValueError('ALGO_QUANTITY_NOT_MATCHED')
    return found

def execute_one(path,tid,*,new_stop_trigger,new_tp_limit,transport=None,
                read_transport=None):
    """One journaled demo request, NEVER a batch or blind retry."""
    base={'state':'BLOCKED','liveWrites':0,'canRetry':False,'stepSent':False}
    with closing(dbopen(path)) as db:
        row=db.execute('SELECT binding,pending FROM replacements WHERE trade_id=?',(tid,)).fetchone()
    if row is None:return {**base,'reason':'UNKNOWN_TRADE'}
    if row['pending'] is not None:return {**base,'reason':'PENDING_OUTCOME_REQUIRES_READBACK'}
    b=json.loads(row['binding'])
    if b.get('symbol')!='BTCUSDT' or b.get('side')!='LONG':
        return {**base,'reason':'DEMO_CANARY_SYMBOL_SIDE_ONLY'}
    try:
        s=snapshot(transport=read_transport)
        positions=[p for p in s['positions'] if str(p.get('id'))==b['positionId']]
        if len(positions)!=1:raise ValueError('POSITION_NOT_UNIQUELY_OBSERVED')
        remaining=Decimal(str(positions[0].get('size')))
        if remaining!=Decimal('0.0001'):raise ValueError('DEMO_CANARY_RESIDUAL_REQUIRED')
        assessment=evaluate(path,tid,positions=s['positions'],
                algos=s['algos'],regular_orders=s['regular_orders'],
                authenticated_sim_readback=True)
        step=assessment.get('nextInstruction')
        if step not in STEPS:raise ValueError('NO_AUTHORIZED_NEXT_STEP')
        if step==STEPS[0]:
            spec=prepare(step,symbol='BTCUSDT',position_side='LONG',
               quantity='0.0001',client_algo_id=b['new_sl_client'],
               trigger_price=new_stop_trigger,execute_price='0')
        elif step==STEPS[3]:
            spec=prepare(step,symbol='BTCUSDT',position_side='LONG',
               quantity='0.0001',client_algo_id=b['new_tp_client'],
               trigger_price=new_tp_limit,execute_price=new_tp_limit)
        else:
            c=b['old_sl_client'] if step==STEPS[1] else b['old_tp_client']
            old=_owned(s['algos'],c)
            order_id=old.get('algoId')
            if not isinstance(order_id,int):
                raise ValueError('EXACT_OLD_ALGO_ID_REQUIRED')
            spec=prepare(step,symbol='BTCUSDT',position_side='LONG',
               quantity='0.0001',client_algo_id='',exact_algo_id=order_id)
        fingerprint=hashlib.sha256(canonical({'step':step,'request':spec}).encode()).hexdigest()
        note_attempt(path,tid,step=step,request_fingerprint=fingerprint)
        # Every network error is uncertain, with a durable pending marker.
        try:
            ack=send_sim_only(step,spec,transport=transport)
        except (UncertainWrite,UnsafeWrite) as err:
            return {**base,'state':'ACK_UNCERTAIN','reason':type(err).__name__,
                    'stepSent':True,'step':step,'pendingReadback':True}
        after=snapshot(transport=read_transport)
        verified=confirm_step(path,tid,step=step,request_fingerprint=fingerprint,
              positions=after['positions'],algos=after['algos'],
              regular_orders=after['regular_orders'],authenticated_sim_readback=True)
        return {**base,**verified,'stepSent':True,'step':step,
                'ackStatus':ack['status'],'pendingReadback':not verified.get('confirmedByReadback',False)}
    except Exception as err:
        return {**base,'reason':str(err) if isinstance(err,ValueError) else type(err).__name__}
