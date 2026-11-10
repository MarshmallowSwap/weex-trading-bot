"""Native WEEX trailing exits built from the existing fee-adjusted net TP.

callbackRate is an API ratio (0.001..0.9999); displayed percentages multiply
by 100. Volatility is sampled at entry, never used to widen an existing order.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from datetime import datetime, timezone

MODE = 'trailing'
OPERATION = 'post_capi_v3_algoOrder'
OPEN_OPERATION = 'get_capi_v3_trailing_openOrders'
HISTORY_OPERATION = 'get_capi_v3_trailing_historyOrders'
TYPES = ('TRAILING_MARKET', 'TRAILING_STOP_MARKET')
ACTIVE = ('NEW', 'UNTRIGGERED', 'UNACTIVATED', 'ACTIVE', 'OPEN', 'PENDING')

def number(value):
    n = Decimal(str(value))
    if not n.is_finite():
        raise ValueError('TRAILING_NONFINITE_NUMBER')
    return n

def is_trailing(plan):
    return (plan.get('exitPolicy') or {}).get('mode') == MODE

def entry_policy(signal, target, *, now=None):
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    observed = datetime.fromisoformat(signal['observedAt']).timestamp()
    candle = int(signal['closedCandleTimes']['5m']) / 1000
    if not 0 <= now-observed <= 60 or not 0 <= now-candle <= 310:
        raise ValueError('TRAILING_VOLATILITY_STALE')
    atr_percent = number(signal['timeframes']['5m']['atrPct'])
    if atr_percent <= 0 or number(target) <= 0:
        raise ValueError('TRAILING_VOLATILITY_INVALID')
    # One 14-period ATR on closed 5m candles, bounded at 0.1%..1% of price.
    ratio = min(Decimal('.01'), max(Decimal('.001'), atr_percent/100))
    ratio = ratio.quantize(Decimal('.0001'), rounding=ROUND_CEILING)
    return {'mode':MODE, 'callbackRate':format(ratio,'f'),
            'activationMode':'AT_NET_TARGET',
            'targetNetProfitUSDT':str(target), 'atrPercent':str(atr_percent),
            'method':'ATR14_5M_CLAMP_0.1_1_PERCENT', 'observedAt':signal['observedAt'],
            'closedCandleTime':signal['closedCandleTimes']['5m']}

def request_from_fixed_tp(fixed, policy, tick):
    """New plans activate at the fee-adjusted fixed TP; legacy plans keep buffer.

    This is a trigger-price estimate, not a guaranteed execution or funding PnL.
    """
    ratio = number(policy['callbackRate']); step = number(tick)
    if not Decimal('.001') <= ratio <= Decimal('.9999') or step <= 0:
        raise ValueError('TRAILING_PARAMETERS_INVALID')
    side = fixed['positionSide']
    if side not in ('LONG','SHORT') or fixed.get('reduceOnly') is not True:
        raise ValueError('TRAILING_CLOSING_POSITION_REQUIRED')
    target = number(fixed['triggerPrice'])
    activation_mode=policy.get('activationMode','BUFFERED_NET_TARGET')
    if activation_mode not in ('AT_NET_TARGET','BUFFERED_NET_TARGET'):
        raise ValueError('TRAILING_ACTIVATION_MODE_INVALID')
    raw = target if activation_mode=='AT_NET_TARGET' else target/(1-ratio if side=='LONG' else 1+ratio)
    rounding = ROUND_CEILING if side=='LONG' else ROUND_FLOOR
    activation = (raw/step).to_integral_value(rounding=rounding)*step
    if activation <= 0 or target <= 0 or number(fixed['quantity']) <= 0:
        raise ValueError('TRAILING_ACTIVATION_UNREACHABLE')
    return {'symbol':fixed['symbol'], 'clientAlgoId':fixed['clientAlgoId'],
            'type':'TRAILING_MARKET', 'side':'SELL' if side=='LONG' else 'BUY',
            'positionSide':side, 'quantity':fixed['quantity'], 'reduceOnly':True,
            'activatePrice':format(activation,'f'), 'callbackRate':format(ratio,'f'),
            'workingType':'MARK_PRICE'}

def normalize(row):
    """Map documented trailing-order observations to lifecycle field names."""
    if row.get('type', row.get('orderType')) not in TYPES:
        raise ValueError('UNEXPECTED_TRAILING_TYPE')
    result = dict(row)
    result.update(algoId=row.get('orderId',row.get('algoId')),
                  clientAlgoId=row.get('clientOrderId',row.get('clientAlgoId')),
                  orderType='TRAILING_MARKET', quantity=row.get('origQty',row.get('quantity')),
                  triggerPrice=row.get('activatePrice'))
    status = row.get('status',row.get('algoStatus'))
    result['algoStatus'] = 'UNTRIGGERED' if status=='UNACTIVATED' else 'NEW' if status in ('ACTIVE','OPEN','PENDING') else status
    # V3 trailing origQty is the submitted base-asset quantity, not book lots.
    result['quantityUnitVerified'] = row.get('quantityUnitVerified') is True or (
        'origQty' in row and number(row['origQty'])>0)
    if not result['algoId'] or not result.get('symbol'):
        raise ValueError('TRAILING_IDENTITY_MISSING')
    if (number(result['quantity'])<=0 or number(result.get('activatePrice'))<=0
            or not Decimal('.001')<=number(result.get('callbackRate'))<=Decimal('.9999')):
        raise ValueError('TRAILING_OBSERVATION_PARAMETERS_INVALID')
    return result

def merge(algos, trailing):
    """Dedicated trailing endpoint is authoritative; reject conflicting overlap."""
    normalized = [normalize(x) for x in trailing]
    result = list(normalized)
    by_id = {str(x['algoId']):x for x in normalized}
    if len(by_id) != len(normalized):raise ValueError('DUPLICATE_TRAILING_ORDER')
    for a in algos:
        existing = by_id.get(str(a.get('algoId')))
        if existing:
            if any(a.get(k)!=existing.get(k) for k in ('clientAlgoId','symbol','side','positionSide','reduceOnly')):
                raise ValueError('CONFLICTING_TRAILING_OBSERVATION')
        else:result.append(a)
    return result

def matches_request(observed, request):
    try:
        return (observed.get('orderType') in TYPES and observed.get('reduceOnly') is True
            and all(observed.get(k)==request[k] for k in ('symbol','side','positionSide','clientAlgoId','workingType'))
            and all(number(observed.get(k))==number(request[k]) for k in ('activatePrice','callbackRate'))
            and number(observed['quantity'])==number(request['quantity']))
    except (KeyError,ValueError,ArithmeticError,TypeError):return False

def description(settings):
    target = number(settings['targetNetProfitUSDT'])
    if settings.get('tpMode') == MODE:
        return (f'TP netto + trailing WEEX: attivazione a +{target:.2f} USDT netti stimati. '
                'Distanza automatica: ATR 5m, tra 0,1% e 1% del prezzo. '
                'Parte dal TP netto impostato, senza margine aggiuntivo. La chiusura può avvenire sotto tale importo; '
                'distanza fissata all’apertura. Funding e slippage esclusi; importo finale non garantito.')
    if settings.get('tpAccountingMode')=='GROSS_BEFORE_COSTS':
        return f'TP fisso lordo: +{target:.2f} USDT prima di fee, slippage e funding (non garantito).'
    return f'TP fisso netto: +{target:.2f} USDT stimati.'
