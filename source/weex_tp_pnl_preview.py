"""Read-only WEEX TP PnL price conversion and transparent validation.

WEEX V3 placeTpSlOrder accepts triggerPrice, not a native USDT PnL field.
This mirrors the existing bot's fee-adjusted pricing, never sends orders.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, InvalidOperation

def n(value):
    try:
        x=Decimal(str(value))
        if not x.is_finite(): raise ValueError('NONFINITE')
        return x
    except (ValueError,TypeError,InvalidOperation):
        raise ValueError('INVALID_TP_INPUT')

def preview(*,side,quantity,entry_cost_usdt,entry_fees_usdt,exit_fee_rate,target_net_usdt,price_tick):
    if side not in ('LONG','SHORT'):raise ValueError('INVALID_SIDE')
    q=n(quantity); cost=n(entry_cost_usdt); fees=n(entry_fees_usdt)
    rate=n(exit_fee_rate); target=n(target_net_usdt); tick=n(price_tick)
    if q<=0 or cost<=0 or fees<0 or target<=0 or tick<=0 or not 0<=rate<1:
        raise ValueError('INVALID_TP_INPUT')
    raw=((cost+fees+target)/(q*(1-rate)) if side=='LONG'
         else (cost-fees-target)/(q*(1+rate)))
    rounding=ROUND_CEILING if side=='LONG' else ROUND_FLOOR
    price=(raw/tick).to_integral_value(rounding=rounding)*tick
    if price<=0:raise ValueError('TP_UNREACHABLE')
    exit_value=q*price
    estimated=(exit_value-cost-fees-exit_value*rate if side=='LONG'
               else cost-exit_value-fees-exit_value*rate)
    if estimated<target:raise ValueError('TP_ROUNDING_UNDER_TARGET')
    return {'mode':'PNL_NET_USDT','targetNetUSDT':str(target),
            'triggerPrice':format(price,'f'),'estimatedNetAtTriggerUSDT':str(estimated),
            'triggerPriceType':'MARK_PRICE','executionPriceGuaranteed':False,
            'fundingIncluded':False,'dispatchAllowed':False}


def gross_preview(*,side,quantity,entry_cost_usdt,entry_fees_usdt,
                  exit_fee_rate,target_gross_usdt,price_tick,
                  estimated_slippage_rate='0'):
    """Gross profit before fees/slippage. Execution remains unguaranteed.

    Gross TP=20 means estimated realized net=20-entry fee-exit fee-
    adverse execution slippage (and funding, if any, must be accounted
    separately). The trigger is price based, not an exchange PnL guarantee.
    """
    if side not in ('LONG','SHORT'):raise ValueError('INVALID_SIDE')
    q=n(quantity);cost=n(entry_cost_usdt);fees=n(entry_fees_usdt)
    rate=n(exit_fee_rate);slip=n(estimated_slippage_rate)
    gross=n(target_gross_usdt);tick=n(price_tick)
    if q<=0 or cost<=0 or fees<0 or gross<=0 or tick<=0 or not 0<=rate<1 or not 0<=slip<1:
        raise ValueError('INVALID_GROSS_TP_INPUT')
    raw=(cost+gross)/q if side=='LONG' else (cost-gross)/q
    rounding=ROUND_CEILING if side=='LONG' else ROUND_FLOOR
    price=(raw/tick).to_integral_value(rounding=rounding)*tick
    if price<=0:raise ValueError('GROSS_TP_UNREACHABLE')
    exit_value=q*price
    gross_at_trigger=exit_value-cost if side=='LONG' else cost-exit_value
    estimated_exit_fee=exit_value*rate
    estimated_slippage=exit_value*slip
    estimated_net=gross_at_trigger-fees-estimated_exit_fee-estimated_slippage
    if gross_at_trigger<gross:raise ValueError('GROSS_TP_ROUNDING_UNDER_TARGET')
    return {'mode':'PNL_GROSS_BEFORE_COSTS_USDT','targetGrossUSDT':str(gross),
            'triggerPrice':format(price,'f'),
            'estimatedGrossAtTriggerUSDT':str(gross_at_trigger),
            'entryFeesUSDT':str(fees),'estimatedExitFeesUSDT':str(estimated_exit_fee),
            'estimatedAdverseSlippageUSDT':str(estimated_slippage),
            'estimatedNetAfterFeesSlippageUSDT':str(estimated_net),
            'fundingIncluded':False,'triggerPriceType':'MARK_PRICE',
            'executionPriceGuaranteed':False,'dispatchAllowed':False}
