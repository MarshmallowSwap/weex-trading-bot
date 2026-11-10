"""Operational segregation evidence for user-attested WEEX manual positions.

This is a read-only policy, not an exchange subaccount. Shared cross margin
remains exposed even if the bot ignores manual positions and their orders.
All observed manual symbols and position identities are reserved. Any
unmatched exposure fails closed; no automatic order changes are authorized.
"""
from weex_live_manual_attestation import classify
from weex_live_position_protection_shadow import assess as protection
def assess(root,positions,regular,algos,*,margin_preference):
    base={'canOpenBotTrade':False,'canTouchManualPosition':False,
          'canTouchManualOrders':False,'liveWrites':0,
          'physicalCollateralIsolation':False}
    if not all(isinstance(x,list) and all(isinstance(r,dict) for r in x)
               for x in (positions,regular,algos)):
        return {**base,'state':'INVALID_ACCOUNT_SNAPSHOT','reasons':['INVALID_ACCOUNT_SNAPSHOT']}
    # Historical manual attestations apply only while those precise
    # positions exist. A flat account has no manual exposure to segregate.
    if not positions and not regular and not algos:
        return {**base,'state':'ACCOUNT_FLAT_NO_LEGACY_MANUAL_EXPOSURE',
                'manualSymbols':[],'reservedSymbols':[],'manualPositions':0,
                'reasons':[],'canRestartBotRecoveryReadOnly':True}
    declared=classify(root,positions)
    guarded=protection(positions,regular,algos)
    manual={x['symbol'] for x in declared.get('positions',[])
            if x.get('manualAttestationMatchesCurrentIdentity')}
    observed={x.get('symbol') for x in positions}
    reasons=[]
    if not declared.get('allPositionsUserAttested'):
        reasons.append('POSITION_IDENTITY_CHANGED_OR_NOT_ATTESTED')
    if margin_preference=='cross':
        reasons.append('CROSS_MARGIN_SHARES_COLLATERAL')
    elif margin_preference!='isolated':
        reasons.append('MARGIN_MODE_NOT_VERIFIED')
    for order in regular+algos:
        if order.get('symbol') in manual:
            # Existing order is left untouched even if it seems to belong
            # to the bot; user attestation takes precedence over guesses.
            continue
        reasons.append('NON_MANUAL_ORDER_PRESENT_REQUIRES_RECONCILIATION')
    if guarded.get('unprotectedCount'):
        reasons.append('MANUAL_POSITIONS_LACK_VERIFIED_STOPS')
    return {**base,'state':'OPERATIONALLY_EXCLUDED_NOT_ISOLATED' if
            declared.get('allPositionsUserAttested') else 'REVIEW_REQUIRED',
            'manualSymbols':sorted(manual),
            'reservedSymbols':sorted(observed|manual),
            'manualPositions':len(manual),
            'reasons':sorted(set(reasons)),
            'canRestartBotRecoveryReadOnly':True,
            'warning':'Cross margin remains account-wide; labeling a position manual does not segregate funds.'}
