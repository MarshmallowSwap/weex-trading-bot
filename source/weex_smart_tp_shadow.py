"""WEEX Smart TP v1: deterministic SHADOW-only exit decision engine.

No exchange client, transport, order mutation, or persistent live state.
Input market metrics must be supplied and timestamp-validated by caller.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

def num(value):
    try:
        x=Decimal(str(value))
        if not x.is_finite(): raise ValueError()
        return x
    except (ValueError,TypeError,InvalidOperation):
        raise ValueError('INVALID_NUMBER')

def evaluate(position,market,settings,*,now_ms):
    """Advisory decision; never authorizes a write or claims an exchange stop."""
    def result(decision,reason,**fields):
        return {'mode':'SHADOW','decision':decision,'reason':reason,
                'dispatchAllowed':False,'ordersSubmitted':False,**fields}
    if not isinstance(position,dict) or not isinstance(market,dict) or not isinstance(settings,dict):
        return result('BLOCK','INVALID_INPUT')
    if settings.get('tpMode')!='adaptive_shadow':
        return result('BLOCK','MODE_NOT_ADAPTIVE_SHADOW')
    if position.get('side') not in ('LONG','SHORT'):
        return result('BLOCK','INVALID_POSITION_SIDE')
    try:
        qty=num(position['quantity']);entry=num(position['entryPrice'])
        entry_fee=num(position['entryFeeUSDT']);mark=num(market['markPrice'])
        fee_rate=num(settings['exitFeeRate']);target=num(settings['targetNetProfitUSDT'])
        atr=num(market['atr']);adx=num(market['adx']);vol=num(market['volumeRatio'])
        strength=num(market['strengthScore']);observed=int(market['observedAtMs'])
        if (qty<=0 or entry<=0 or mark<=0 or atr<=0 or entry_fee<0
            or not Decimal('0')<=fee_rate<=Decimal('.01')
            or target<=0 or not 0<=strength<=100 or not 0<=adx<=100 or vol<0
            or not 0<=now_ms-observed<=30000):
            return result('BLOCK','INVALID_OR_STALE_MARKET')
        # Mark-based estimated net PnL; execution price may differ.
        gross=(mark-entry)*qty if position['side']=='LONG' else (entry-mark)*qty
        net=gross-entry_fee-(mark*qty*fee_rate)
        score=(strength*Decimal('.5')
               +min(Decimal(100),adx*2)*Decimal('.3')
               +min(Decimal(100),vol*Decimal(50))*Decimal('.2'))
        if net<target:
            return result('WAIT','NET_TARGET_NOT_REACHED',estimatedNetUSDT=str(net),
                          targetNetUSDT=str(target),trendScore=str(score))
        if score<Decimal(45):
            return result('FIXED_EXIT_CANDIDATE','WEAK_TREND',estimatedNetUSDT=str(net),
                          trendScore=str(score))
        multiplier=Decimal('1.0') if score<70 else Decimal('1.5')
        distance=atr*multiplier
        # Advisory trailing stop from current mark. A *separate* stateful engine
        # must track favorable peak/trough and guarantee stop monotonicity.
        suggested=(mark-distance if position['side']=='LONG' else mark+distance)
        return result('TRAILING_CANDIDATE','TREND_CONFIRMED',
                      estimatedNetUSDT=str(net),trendScore=str(score),
                      atrMultiplier=str(multiplier),proposedStopPrice=str(suggested),
                      stopIsActiveOnExchange=False)
    except (KeyError,ValueError,TypeError,OverflowError):
        return result('BLOCK','INVALID_INPUT_FIELDS')

def advance_trailing(previous, *, side, mark_price, atr, multiplier):
    """Pure shadow trailing peak and stop update, no exchange orders.

    Stop is monotone: LONG non-decreasing, SHORT non-increasing.
    Use with sequential authenticated price observations; missing observations
    are not permission to claim a protected position.
    """
    if side not in ('LONG','SHORT'):
        raise ValueError('INVALID_SIDE')
    px=num(mark_price);v=num(atr);k=num(multiplier)
    if px<=0 or v<=0 or not Decimal('.5')<=k<=Decimal('4'):
        raise ValueError('INVALID_TRAIL_PARAMETERS')
    if previous is None:
        peak=px
        stop=px-v*k if side=='LONG' else px+v*k
    else:
        if not isinstance(previous,dict) or previous.get('side')!=side:
            raise ValueError('TRAIL_IDENTITY_CHANGED')
        old_peak=num(previous['favorableExtreme'])
        old_stop=num(previous['stopPrice'])
        if side=='LONG':
            peak=max(old_peak,px)
            stop=max(old_stop,peak-v*k)
        else:
            peak=min(old_peak,px)
            stop=min(old_stop,peak+v*k)
    if stop<=0:
        raise ValueError('STOP_PRICE_INVALID')
    return {'side':side,'favorableExtreme':str(peak),'stopPrice':str(stop),
            'mode':'SHADOW','dispatchAllowed':False,'stopIsActiveOnExchange':False}
