"""Recover exact WEEX pilot entry/close dispatches from authenticated GET evidence.

Never re-sends, never invents an executed order, and never clears an UNKNOWN
state without a journal-matching clientId and completely bound fills.
"""
import json
from decimal import Decimal,InvalidOperation
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_attached_stop_evidence import protected_entry

def reconcile(db,pilot_id,stage,*,order, fills, positions, regular_orders, conditional_orders):
    if stage not in ('entry','close'):raise ValueError('UNKNOWN_STAGE')
    if not all(isinstance(x,list) for x in (fills,positions,regular_orders,conditional_orders)):
        raise ValueError('ACCOUNT_OBSERVATION_INCOMPLETE')
    with closing(connect(db)) as c:
        c.execute('BEGIN IMMEDIATE')
        pilot=c.execute('SELECT side,quantity,entry_id,close_id,state,proposals FROM pilot_v1 WHERE pilot_id=?',
                        (pilot_id,)).fetchone()
        if not pilot:
            c.rollback();raise ValueError('UNKNOWN_PILOT')
        side,quantity,entry_id,close_id,pilot_state,raw_proposals=pilot
        table='pilot_entry_dispatch_v1' if stage=='entry' else 'pilot_close_dispatch_v1'
        col='client_id' if stage=='entry' else 'close_client_id'
        try: row=c.execute('SELECT state FROM '+table+' WHERE pilot_id=?',(pilot_id,)).fetchone()
        except Exception:
            c.rollback()
            return {'state':'NO_DISPATCH_RECORD','confirmed':False,'canRetry':False}
        if row is None:
            c.rollback();return {'state':'NO_DISPATCH_RECORD','confirmed':False,'canRetry':False}
        if row[0]=='EXCHANGE_FILLED_RECONCILED':
            c.rollback();return {'state':'ALREADY_RECONCILED','confirmed':True,'canRetry':False}
        cid=entry_id if stage=='entry' else close_id
        if not isinstance(order,dict) or not order:
            c.rollback()
            return {'state':'EXCHANGE_ORDER_NOT_OBSERVED','confirmed':False,'canRetry':False}
        try:
            oid=str(order['orderId'])
            qty=Decimal(str(quantity))
            observed=Decimal(str(order['executedQty']))
            total=sum((Decimal(str(f['qty'])) for f in fills),Decimal(0))
            fill_ids=[str(f['id']) for f in fills]
            direction=('BUY' if side=='LONG' else 'SELL') if stage=='entry' else ('SELL' if side=='LONG' else 'BUY')
            ok=(cid==order['clientOrderId'] and oid and order['symbol']=='ETHUSDT'
                and order['positionSide']==side and order['side']==direction
                and order['type']=='MARKET' and order['status']=='FILLED'
                and (order.get('reduceOnly') is True if stage=='close' else order.get('reduceOnly') is not True)
                and qty>0 and qty==observed==total and fills and len(fill_ids)==len(set(fill_ids))
                and all(f['symbol']=='ETHUSDT' and str(f['orderId'])==oid
                    and f['positionSide']==side and f['side']==direction for f in fills))
            if stage=='entry':
                prepared_entry=json.loads(raw_proposals).get('entry',{})
                has_attached_stop='slTriggerPrice' in prepared_entry
                stop_evidence=(protected_entry(json.loads(raw_proposals),order,conditional_orders,
                                               side,quantity) if has_attached_stop else None)
                ok=ok and len(positions)==1 and not regular_orders and (
                    stop_evidence.get('verified') is True if has_attached_stop else not conditional_orders)
                if ok:
                    p=positions[0]
                    ok=(p['symbol']=='ETHUSDT' and p['side']==side
                        and Decimal(str(p['size']))==qty
                        and p['marginType'] in ('ISOLATED','ISOLATE') and bool(p.get('id')))
            else:
                ok=ok and not positions and not regular_orders and not conditional_orders
        except (KeyError,TypeError,ValueError,InvalidOperation,ArithmeticError):
            ok=False
        if not ok:
            c.rollback()
            return {'state':'EXCHANGE_EVIDENCE_INCOMPLETE_OR_CONTRADICTORY','confirmed':False,'canRetry':False}
        # Never transition an unrecognized state, and never mistake an HTTP ACK
        # for a fill. This is the only writer of EXCHANGE_FILLED_RECONCILED.
        c.execute('UPDATE '+table+' SET state=? WHERE pilot_id=? AND state IN (?,?)',
                  ('EXCHANGE_FILLED_RECONCILED',pilot_id,'ACK_RECEIVED_UNRECONCILED','OUTCOME_UNKNOWN'))
        if c.total_changes!=1:
            c.rollback()
            return {'state':'INVALID_DISPATCH_STATE','confirmed':False,'canRetry':False}
        if stage=='entry':
            c.execute('UPDATE pilot_v1 SET state=? WHERE pilot_id=? AND state=?',
                      ('ENTRY_RECONCILED_EXTERNALLY',pilot_id,'PREPARED_NO_SEND'))
        else:
            c.execute('UPDATE pilot_v1 SET state=? WHERE pilot_id=?',
                      ('CLOSED_VERIFIED_EXTERNALLY',pilot_id))
        c.commit()
        # Exchange fill identity is not sufficient to certify that a position
        # was exclusively created by this pilot. Independent baseline-based
        # ownership attestation is still required before any close transport.
        return {'state':'EXCHANGE_FILLED_RECONCILED','confirmed':True,
                'clientOrderId':cid,'orderId':oid,'canRetry':False,
                'canSendNextStage':False,'requiresOwnershipAttestation':stage=='entry'}
