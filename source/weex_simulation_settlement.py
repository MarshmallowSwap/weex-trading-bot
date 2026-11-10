"""Empirical settlement evidence for one minimum-size BTC simulation cycle only.

The raw false forwardContractFlag is preserved. This does not authorize orders,
validate production, or extrapolate the observation to larger strategy positions.
"""
from datetime import datetime, timezone
from decimal import Decimal as D

SIM = 'https://api-sim.weex.com'

def number(value):
    value = D(str(value))
    if not value.is_finite():
        raise ValueError('NONFINITE_SETTLEMENT_VALUE')
    return value

def validate_empirical_contract(meta, evidence, *, source_host, checked_at=None):
    if source_host != SIM or evidence.get('host') != SIM:
        raise PermissionError('SIMULATION_SETTLEMENT_HOST_REQUIRED')
    current = checked_at or datetime.now(timezone.utc)
    age = (current - datetime.fromisoformat(evidence['finishedAt'])).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError('SETTLEMENT_EVIDENCE_EXPIRED')
    expected = {'symbol':'BTCUSDT', 'baseAsset':'BTC', 'quoteAsset':'USDT',
                'marginAsset':'USDT', 'contractType':'PERPETUAL',
                'forwardContractFlag':False, 'quantityPrecision':4}
    if any(meta.get(k) != v for k,v in expected.items()):
        raise ValueError('SETTLEMENT_CONTRACT_SCOPE_MISMATCH')
    if evidence.get('metadataFlag') is not False or evidence.get('status') != 'CLOSED_VERIFIED':
        raise ValueError('SETTLEMENT_CALIBRATION_INCOMPLETE')
    if evidence.get('finalInventory') != {'positions':0,'ordinaryOrders':0,'conditionalOrders':0}:
        raise ValueError('SETTLEMENT_CALIBRATION_NOT_FLAT')
    quantity = D('0.0001')
    if number(meta['minOrderSize']) != quantity or number(meta['maxLeverage']) != 200:
        raise ValueError('SETTLEMENT_LIMITS_CHANGED')
    for key in ('pricePrecision','quantityPrecision'):
        if type(meta[key]) is not int or not -12 <= meta[key] <= 18:
            raise ValueError('INVALID_CONTRACT_PRECISION')
    if number(meta['contractVal']) != quantity:
        raise ValueError('SETTLEMENT_CONTRACT_VALUE_CHANGED')
    if min(number(meta[k]) for k in ('maxOrderSize','marketOpenLimitSize')) < quantity:
        raise ValueError('SETTLEMENT_QUANTITY_NOT_PERMITTED')
    entry, close = evidence['entryObservation'], evidence['exitObservation']
    values, fees, pnls = [], [], []
    for order, fills, side in [(entry,evidence['entryFills'],'BUY'),(close,evidence['exitFills'],'SELL')]:
        if (order['symbol'] != 'BTCUSDT' or order['positionSide'] != 'LONG'
                or order['side'] != side or order['status'] != 'FILLED'
                or number(order['executedQty']) != quantity or not fills):
            raise ValueError('SETTLEMENT_ORDER_BINDING')
        ids=set(); qty=D(0); value=D(0); fee=D(0); pnl=D(0)
        for f in fills:
            if (str(f['orderId']) != str(order['orderId']) or f['symbol'] != 'BTCUSDT'
                    or f['side'] != side or f['positionSide'] != 'LONG'
                    or f['commissionAsset'] != 'USDT' or str(f['id']) in ids):
                raise ValueError('SETTLEMENT_FILL_BINDING')
            ids.add(str(f['id']))
            q, price = number(f['qty']), number(f['price'])
            if q <= 0 or price <= 0 or number(f['quoteQty']) != q*price or number(f['commission']) < 0:
                raise ValueError('SETTLEMENT_NONLINEAR_FILL')
            qty+=q; value+=q*price; fee+=number(f['commission']); pnl+=number(f['realizedPnl'])
        if qty != quantity or value != number(order['cumQuote']):
            raise ValueError('SETTLEMENT_FILL_TOTAL')
        values.append(value); fees.append(fee); pnls.append(pnl)
    position=evidence['positionDuring']
    if (close['reduceOnly'] is not True or position['asset'] != 'USDT'
            or position['symbol'] != 'BTCUSDT' or position['side'] != 'LONG'
            or number(position['size']) != quantity or number(position['leverage']) != 200
            or number(position['openValue']) != values[0]
            or number(position['openFee']) != fees[0]
            or pnls[0] != 0 or pnls[1] != values[1]-values[0]
            or abs(number(position['marginSize'])-values[0]/200) >= D('0.0001')):
        raise ValueError('SETTLEMENT_ACCOUNTING_MISMATCH')
    return {'quantityStep':quantity,'priceTick':D(1).scaleb(-meta['pricePrecision']),
            'minQuantity':quantity,'maxQuantity':quantity,
            'minLeverage':D(200),'maxLeverage':D(200),
            'validationMethod':'EMPIRICAL_MINIMUM_BTC_SIMULATION_ONLY',
            'rawForwardContractFlag':False,'strategySizeValidated':False,
            'evidenceFinishedAt':evidence['finishedAt']}
