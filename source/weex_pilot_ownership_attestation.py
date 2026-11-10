"""Exact ownership attestation for a single Isolated 1x pilot position.

The owner flag comes from immutable before/after snapshots, unique client order
and fills. Never trust a caller-provided manualOrMixed field as evidence alone.
Does not place or close orders.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime,timezone

def attest(*,baseline,position,entry,fill_rows,pilot):
    deny=lambda why:{'owned':False,'reason':why,'exchangeWrites':0}
    if not isinstance(baseline,dict) or not all(isinstance(x,dict) for x in (position,entry,pilot)):
        return deny('MISSING_VERIFIABLE_OBSERVATIONS')
    if not isinstance(fill_rows,list) or not fill_rows:return deny('FILLS_NOT_OBSERVED')
    if any(not isinstance(baseline.get(k),list) or baseline[k] for k in ('positions','regularOrders','conditionalOrders')):
        return deny('BASELINE_NOT_FLAT')
    if baseline.get('snapshotVerified') is not True or baseline.get('account')!='CURRENT_WEEX':
        return deny('BASELINE_NOT_ATTESTED')
    try:
        btime=int(baseline['observedAtMs'])
        ordertime=int(entry['time'])
        ptime=int(position['createdTime'])
        qty=Decimal(str(pilot['quantity']))
        filled=sum((Decimal(str(f['qty'])) for f in fill_rows),Decimal(0))
        pos_qty=Decimal(str(position['size']))
        order_qty=Decimal(str(entry['executedQty']))
        if not all(v.is_finite() and v>0 for v in (qty,filled,pos_qty,order_qty)):
            return deny('INVALID_QUANTITY')
        if qty!=filled or qty!=pos_qty or qty!=order_qty:return deny('QUANTITY_NOT_EXACT')
        if not btime<=ptime<=max(int(f['time']) for f in fill_rows)+10000:
            return deny('POSITION_TIMESTAMP_NOT_BOUND')
        if ordertime<btime:return deny('ENTRY_PREDATES_BASELINE')
        if not (pilot['entryId']==entry['clientOrderId']
                and entry['status']=='FILLED'
                and entry['symbol']==position['symbol']=='ETHUSDT'
                and pilot['side']==entry['positionSide']==position['side']
                and entry['side']==('BUY' if pilot['side']=='LONG' else 'SELL')
                and position['marginType'] in ('ISOLATED','ISOLATE')
                and position.get('id') and str(position['id'])!='0'):
            return deny('ENTRY_POSITION_IDENTITY_MISMATCH')
        oid=str(entry['orderId'])
        ids=[str(f['id']) for f in fill_rows]
        if len(ids)!=len(set(ids)) or any(not i for i in ids):
            return deny('FILL_IDS_INVALID')
        if any(str(f['orderId'])!=oid or f['symbol']!='ETHUSDT'
               or f['positionSide']!=pilot['side'] or f['side']!=entry['side']
               or not btime<=int(f['time']) for f in fill_rows):
            return deny('FILL_IDENTITY_UNBOUND')
        return {'owned':True,'positionId':str(position['id']),
                'entryOrderId':oid,'clientOrderId':pilot['entryId'],
                'quantity':str(qty),'exchangeWrites':0,
                'basis':'FLAT_BASELINE_EXACT_ENTRY_FILLS_AND_POSITION'}
    except (KeyError,ValueError,TypeError,InvalidOperation,OverflowError):
        return deny('MALFORMED_EVIDENCE')
