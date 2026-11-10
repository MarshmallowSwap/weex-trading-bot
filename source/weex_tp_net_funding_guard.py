"""WEEX fee/funding-aware net TP for a remaining USDT-linear position.

Pure calculation and policy: no SDK, network, credentials or order dispatch.
Positive funding_paid = cost; negative = credit. For partial exits the
realized_net_before_funding is net of allocated ENTRY and EXIT commissions;
realized_funding_paid is the signed funding assigned to closed quantities.
The remaining position cost/entry-fee must be verified against executed
entry fills and previous partial closes, not blindly pro-rated by a caller.
"""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

def dec(v):
    try:
        d=Decimal(str(v))
        if not d.is_finite():raise ValueError('NONFINITE')
        return d
    except (InvalidOperation,TypeError,ValueError):
        raise ValueError('INVALID_DECIMAL')

def build(*,side,remaining_qty,remaining_entry_value,remaining_entry_fees,
          remaining_funding_paid,realized_net_before_funding,
          realized_funding_paid,exit_fee_rate,limit_tick,target_net_usdt,
          funding_evidence_verified=False,entry_evidence_verified=False,
          exit_fee_evidence_verified=False,partial_exit_evidence_verified=False,
          expected_exit_slippage_rate='0'):
    base={'state':'BLOCKED','canSubmit':False,'liveEntryAllowed':False,
          'orderExecutionGuaranteed':False,'stopLossCertified':False,
          'ocoCertified':False,'fundingIncluded':False}
    if not all((funding_evidence_verified,entry_evidence_verified,
                exit_fee_evidence_verified,partial_exit_evidence_verified)):
        return {**base,'reason':'MISSING_VERIFIED_FUNDING_FEES_OR_PARTIAL_FILLLS'}
    if side not in ('LONG','SHORT'):return {**base,'reason':'INVALID_SIDE'}
    try:
        q=dec(remaining_qty);cost=dec(remaining_entry_value)
        fee_in=dec(remaining_entry_fees);f_rem=dec(remaining_funding_paid)
        realized=dec(realized_net_before_funding);f_real=dec(realized_funding_paid)
        fee_out=dec(exit_fee_rate);slip=dec(expected_exit_slippage_rate)
        tick=dec(limit_tick);target=dec(target_net_usdt)
        if (q<=0 or cost<=0 or fee_in<0 or tick<=0 or target<=0
           or not Decimal('0')<=fee_out<Decimal('.1')
           or not Decimal('0')<=slip<Decimal('.1')):
            raise ValueError('INVALID_PARAMETERS')
        # Net already achieved on partial closes, including realized funding.
        already=realized-f_real
        still_required=target-already
        # Exit fee/slippage bounds must be conservative for the chosen execution
        # type. LIMIT fills and MARK_PRICE triggers are not guaranteed.
        rate=fee_out+slip
        if rate>=1:raise ValueError('UNSAFE_RATE')
        if side=='LONG':
            raw=(cost+fee_in+f_rem+still_required)/(q*(1-rate))
            px=(raw/tick).to_integral_value(rounding=ROUND_CEILING)*tick
            net_remaining=q*px-cost-fee_in-f_rem-q*px*rate
        else:
            raw=(cost-fee_in-f_rem-still_required)/(q*(1+rate))
            px=(raw/tick).to_integral_value(rounding=ROUND_FLOOR)*tick
            net_remaining=cost-q*px-fee_in-f_rem-q*px*rate
        if px<=0:
            return {**base,'reason':'TARGET_PRICE_NOT_REACHABLE'}
        combined=already+net_remaining
        if combined<target:raise ValueError('ROUNDING_BELOW_TARGET')
        return {**base,'state':'FUNDING_AWARE_TP_PREVIEW_ONLY',
                'reason':'AWAIT_EXCHANGE_ORDER_PAIR_AND_STOP_PROOF',
                'side':side,'remainingQty':str(q),'targetNetUSDT':str(target),
                'previousRealizedNetUSDT':str(already),
                'remainingTargetUSDT':str(still_required),
                'tpLimitPrice':format(px,'f'),
                'theoreticalTotalNetAtLimitUSDT':str(combined),
                'remainingFundingPaidUSDT':str(f_rem),
                'realizedFundingPaidUSDT':str(f_real),
                'fundingIncluded':True,'executionPriceGuaranteed':False,
                'canSubmit':False}
    except ValueError as exc:
        return {**base,'reason':str(exc)}
