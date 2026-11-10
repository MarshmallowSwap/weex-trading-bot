"""Maximize permitted leverage first; fit quantity within margin and tier limits."""
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
from weex_margin_sizing import contract_rules

MINIMUM=Decimal(100)

def number(value):
    result=Decimal(str(value))
    if not result.is_finite():raise ValueError('NONFINITE_LEVERAGE_INPUT')
    return result

def select(*,metadata,brackets,margin_usdt=None,reference_price,minimum=100,cost_usdt=None,entry_fee_rate=None):
    rules=contract_rules(metadata)
    cost_mode = cost_usdt is not None
    if cost_mode and margin_usdt is not None:
        raise ValueError('AMBIGUOUS_BUDGET')
    margin=number(cost_usdt if cost_mode else margin_usdt);price=number(reference_price)
    fee=number(entry_fee_rate) if cost_mode else Decimal(0)
    if not 0 <= fee < 1:raise ValueError('INVALID_ENTRY_FEE')
    minimum=max(MINIMUM,number(minimum),rules['minLeverage'])
    if margin<=0 or price<=0:raise ValueError('INVALID_MARGIN_OR_PRICE')
    if not isinstance(brackets,list) or not brackets:raise ValueError('LEVERAGE_TIERS_REQUIRED')
    tiers=[]
    for b in brackets:
        floor,cap,maximum=(number(b[k]) for k in ('notionalFloor','notionalCap','initialLeverage'))
        if floor<0 or cap<=floor or maximum<=0:raise ValueError('INVALID_RISK_BRACKET')
        tiers.append((floor,cap,maximum))
    tiers.sort()
    if any(tiers[i][0]<tiers[i-1][1] for i in range(1,len(tiers))):raise ValueError('OVERLAPPING_RISK_BRACKETS')
    candidates=sorted({min(rules['maxLeverage'],x[2]) for x in tiers},reverse=True)
    step=rules['quantityStep']
    for lev in candidates:
        if lev<minimum:continue
        available_margin=margin/(1+lev*fee) if cost_mode else margin
        budget_qty=min(available_margin*lev/price,rules['maxQuantity'])
        best=None
        for floor,cap,maximum in tiers:
            if lev>maximum:continue
            # Bracket cap is exclusive. Always round to a valid quantity step below it.
            cap_steps=(cap/(price*step)).to_integral_value(rounding=ROUND_CEILING)-1
            qty=min((budget_qty/step).to_integral_value(rounding=ROUND_FLOOR),cap_steps)*step
            notional=qty*price
            if qty<=0 or qty<rules['minQuantity'] or not floor<=notional<cap:continue
            if best is None or qty>best[0]:best=(qty,notional,cap)
        if best:
            qty,notional,cap=best
            result = {'quantity':format(qty,'f'),'initialMarginUSDT':format(notional/lev,'f'),
                    'notionalUSDT':format(notional,'f'),'leverage':format(lev,'f'),
                    'targetMarginUSDT':format(available_margin,'f'),'quantityStep':str(step),'priceTick':str(rules['priceTick']),
                    'requiresExchangeLeverageAndContractStepVerification':True,
                    'policy':'MAXIMUM_LEVERAGE_FIRST_MINIMUM_100',
                    'minimumLeverage':str(minimum),'advertisedMaxLeverage':str(rules['maxLeverage']),
                    'quantityCappedByTier':qty<(available_margin*lev/price/step).to_integral_value(rounding=ROUND_FLOOR)*step
                                            and cap<=available_margin*lev,
                    'selectedTierNotionalCap':str(cap),'accountLeverageConfirmed':False}
            if cost_mode:
                result.update(budgetMode='COST_INCLUDING_ENTRY_FEE',targetCostUSDT=str(margin),
                              estimatedEntryFeeUSDT=str(notional*fee),
                              estimatedCostUSDT=str(notional/lev+notional*fee),
                              entryFeeRate=str(fee))
            return result
    raise ValueError('NO_VALID_QUANTITY_AT_LEVERAGE_100_OR_HIGHER')
