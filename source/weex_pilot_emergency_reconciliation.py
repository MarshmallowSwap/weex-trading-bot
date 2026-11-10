"""Exchange-readback reconciliation of journaled one-shot closePositions.

A success HTTP response is NOT a close proof. Requires the exact
exchange-generated close order, fills, and an independently flat account.
Unknown outcome stays UNKNOWN; no retry.
"""
import json
from decimal import Decimal,InvalidOperation
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect

def reconcile_emergency(db,pilot_id,*,order,fills,positions,regular,conditional,
                        expected_stop_algo_id=None,terminal_stop_history=None):
    deny=lambda why:{'confirmed':False,'state':why,'canRetry':False}
    # For active-stop closes, absence from open orders is not sufficient.
    # Require exchange history to bind the exact original stop to CANCELED
    # (WEEX demonstrated this status after positionId close in API-SIM).
    if expected_stop_algo_id is not None:
        if (not isinstance(expected_stop_algo_id,str) or not expected_stop_algo_id
            or not isinstance(terminal_stop_history,list)):
            return deny('ATTACHED_STOP_TERMINAL_HISTORY_MISSING')
        matches=[x for x in terminal_stop_history if isinstance(x,dict)
            and str(x.get('algoId'))==expected_stop_algo_id]
        if len(matches)!=1 or str(matches[0].get('algoStatus')) not in ('CANCELED','CANCELLED'):
            return deny('ATTACHED_STOP_TERMINAL_HISTORY_UNVERIFIED')
    if not all(isinstance(x,list) for x in (fills,positions,regular,conditional)):
        return deny('EXCHANGE_DATA_INCOMPLETE')
    with closing(connect(db)) as c:
        c.execute('BEGIN IMMEDIATE')
        names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pilot_emergency_dispatch_v1' not in names:
            c.rollback();return deny('NO_EMERGENCY_DISPATCH')
        row=c.execute('SELECT position_id,state,response FROM pilot_emergency_dispatch_v1 WHERE pilot_id=?',
                      (pilot_id,)).fetchone()
        p=c.execute('SELECT side,quantity,state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if row is None or p is None:
            c.rollback();return deny('JOURNAL_NOT_FOUND')
        position_id,state,response=row
        side,qty,pstate=p
        if state=='EXCHANGE_FILLED_RECONCILED':
            c.rollback();return {'confirmed':True,'state':'ALREADY_RECONCILED','canRetry':False}
        if state!='ACK_RECEIVED_NEEDS_EXCHANGE_READBACK' or not response:
            c.rollback();return deny('ACK_MISSING_OR_OUTCOME_UNKNOWN')
        # A flat position with an open conditional order is not a completed
        # pilot lifecycle. Do not mark the close reconciled or delete the stop.
        if not positions and conditional:
            c.rollback();return deny('ACCOUNT_FLAT_BUT_CONDITIONAL_ORDER_REMAINS')
        ack=json.loads(response)
        if not isinstance(order,dict):
            c.rollback();return deny('CLOSE_ORDER_NOT_OBSERVED')
        try:
            oid=str(ack['orderId'])
            expected_side='SELL' if side=='LONG' else 'BUY'
            filled=Decimal(str(order['executedQty']))
            expected_qty=Decimal(str(qty))
            total=sum((Decimal(str(f['qty'])) for f in fills),Decimal(0))
            ids=[str(f['id']) for f in fills]
            correct=(str(order['orderId'])==oid and order['symbol']=='ETHUSDT'
                     and order['positionSide']==side and order['side']==expected_side
                     and order['status']=='FILLED' and order.get('reduceOnly') is True
                     and expected_qty>0 and filled==total==expected_qty and bool(fills)
                     and all(x and x!='None' for x in ids) and len(ids)==len(set(ids))
                     and all(str(f['orderId'])==oid and f['symbol']=='ETHUSDT'
                             and f['positionSide']==side and f['side']==expected_side for f in fills)
                     and not positions and not regular and not conditional)
        except (KeyError,TypeError,ValueError,InvalidOperation,ArithmeticError):
            correct=False
        if not correct:
            c.rollback();return deny('CLOSE_EVIDENCE_INCOMPLETE_OR_MISMATCHED')
        c.execute("UPDATE pilot_emergency_dispatch_v1 SET state='EXCHANGE_FILLED_RECONCILED' WHERE pilot_id=?",
                  (pilot_id,))
        c.execute("UPDATE pilot_v1 SET state='CLOSED_VERIFIED_EXTERNALLY' WHERE pilot_id=?",(pilot_id,))
        c.commit()
        return {'confirmed':True,'state':'EXCHANGE_FILLED_RECONCILED',
                'positionId':position_id,'orderId':oid,'canRetry':False}


def reconcile_active_stop_emergency(db,pilot_id,*,stop_algo_id,stop_history,
                                    order,fills,positions,regular,conditional):
    """Mandatory terminal stop proof for the active-stop positionId pathway."""
    if not stop_algo_id or not isinstance(stop_history,list):
        return {'confirmed':False,'state':'ATTACHED_STOP_TERMINAL_HISTORY_MISSING',
                'canRetry':False}
    return reconcile_emergency(db,pilot_id,order=order,fills=fills,
        positions=positions,regular=regular,conditional=conditional,
        expected_stop_algo_id=str(stop_algo_id),terminal_stop_history=stop_history)
