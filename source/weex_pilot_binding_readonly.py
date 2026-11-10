"""Read-only matching of isolated pilot client IDs to observed WEEX order rows.

Never sends orders, changes pilot state, or grants execution approval.
"""
import json
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

def inspect(journal_path, orders):
    path=Path(journal_path)
    result={'state':'NO_PILOT_JOURNAL','pilots':0,'stages':[],
            'canSend':False,'canRetry':False,'exchangeWrites':0}
    if not path.is_file():
        return result
    db=sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pilot_v1' in tables:
            pilots=db.execute('SELECT pilot_id,side,quantity,entry_id,stop_id,close_id FROM pilot_v1').fetchall()
            kind='ISOLATED_PILOT'
        elif 'reservations' in tables:
            reservations=db.execute('SELECT signal_id,client_id,symbol,state FROM reservations').fetchall()
            pilots=[]
            kind='SDK_RESERVATIONS'
        else:
            return {**result,'state':'PILOT_SCHEMA_MISSING'}
    finally:
        db.close()
    if kind=='SDK_RESERVATIONS':
        stages=[]
        for signal,cid,symbol,local_state in reservations:
            matches=[o for o in orders if isinstance(o,dict) and
                     str(o.get('clientOrderId') or '')==cid]
            status='UNVERIFIED'
            if len(matches)>1:
                status='AMBIGUOUS'
            elif len(matches)==1:
                row=matches[0]
                status=('OBSERVED_UNATTESTED' if
                        row.get('symbol')==symbol=='ETHUSDT' and row.get('orderId')
                        else 'MISMATCH')
            stages.append({'pilotId':signal,'stage':'entry','state':status,
                           'reservationState':local_state})
        return {**result,'state':'READ_ONLY_SDK_RESERVATION_AUDIT',
                'pilots':len(reservations),'stages':stages}
    stages=[]
    for pid,side,qty,entry,stop,close in pilots:
        for stage,cid,field in (('entry',entry,'clientOrderId'),
                                ('stop',stop,'clientAlgoId'),
                                ('close',close,'clientOrderId')):
            rows=[o for o in orders if isinstance(o,dict) and str(o.get(field) or '')==cid]
            state='UNVERIFIED'
            if len(rows)>1:
                state='AMBIGUOUS'
            elif len(rows)==1:
                r=rows[0]
                try:
                    valid=(r.get('symbol')=='ETHUSDT' and r.get('positionSide')==side
                           and Decimal(str(r.get('origQty',r.get('quantity'))))==Decimal(qty)
                           and bool(r.get('orderId') or r.get('algoId')))
                    if stage!='entry':
                        valid=valid and r.get('reduceOnly') is True
                    if stage=='close':
                        # A reduceOnly flag alone is not proof of a filled exit.
                        # Require the closing side, complete fills and exact qty.
                        expected_side='SELL' if side=='LONG' else 'BUY'
                        actual=Decimal(str(r.get('executedQty')))
                        valid=(valid and r.get('side')==expected_side
                               and str(r.get('status','')).upper()=='FILLED'
                               and actual.is_finite() and actual==Decimal(qty))
                    state='OBSERVED_UNATTESTED' if valid else 'MISMATCH'
                except (InvalidOperation,ValueError,TypeError):
                    state='MISMATCH'
            stages.append({'pilotId':pid,'stage':stage,'state':state})
    return {**result,'state':'READ_ONLY_AUDIT','pilots':len(pilots),'stages':stages}
