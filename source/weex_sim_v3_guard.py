"""WEEX Futures V3 dedicated simulation endpoint safety firewall.

Official WEEX Futures docs specify api-sim.weex.com with V3 paths.
Do not reuse legacy /sim/ paths or production keys implicitly.
This module NEVER sends requests or creates authenticated sessions.
"""
from urllib.parse import urlsplit
SIM_HOST='api-sim.weex.com'
LIVE_HOST='api-contract.weex.com'
READ_PATHS=frozenset((
    '/capi/v3/account/position/allPosition',
    '/capi/v3/account/balance',
    '/capi/v3/openOrders',
    '/capi/v3/openAlgoOrders',
    '/capi/v3/order',
    '/capi/v3/order/history',
    '/capi/v3/userTrades',
    '/capi/v3/allAlgoOrders',
    '/capi/v3/market/exchangeInfo',
    '/capi/v3/market/time'))
WRITE_PATHS=frozenset((
    '/capi/v3/order',
    '/capi/v3/placeTpSlOrder',
    '/capi/v3/closePositions'))

def assess(method,url,*,simulation_credentials_verified=False,
           isolated_account_verified=False,exit_verified=False,
           conditional_pair_verified=False):
    """No write authorization: verification gates remain external and unmet."""
    result={'allowed':False,'ordersSubmitted':False,'canTrade':False,
            'writesEnabled':False,'environment':'SIMULATION_V3'}
    if not isinstance(url,str) or not isinstance(method,str):
        return {**result,'reason':'INVALID_REQUEST'}
    u=urlsplit(url)
    if (u.scheme!='https' or u.netloc!=SIM_HOST or u.fragment
            or u.username is not None or u.password is not None):
        return {**result,'reason':'NOT_DEDICATED_SIMULATION_DOMAIN'}
    if '/sim/' in u.path:
        return {**result,'reason':'LEGACY_SIM_PATH_NOT_SUPPORTED_ON_DEDICATED_DOMAIN'}
    if method=='GET' and u.path in READ_PATHS:
        return {**result,'allowed':True,'reason':'SIMULATION_GET_ONLY'}
    if u.path in WRITE_PATHS and method in ('POST','DELETE'):
        missing=[]
        if not simulation_credentials_verified:missing.append('SIM_CREDENTIALS_NOT_VERIFIED')
        if not isolated_account_verified:missing.append('SIM_ACCOUNT_NOT_ISOLATED')
        if not exit_verified:missing.append('SIM_SAFE_EXIT_UNVERIFIED')
        if not conditional_pair_verified:missing.append('SIM_TP_SL_PAIR_UNVERIFIED')
        # This firewall can never authorize a write, even after flags are set.
        return {**result,'reason':'WRITE_NOT_IMPLEMENTED',
                'unverified':missing}
    return {**result,'reason':'UNSUPPORTED_SIMULATION_OPERATION'}

def audit():
    """Machine-readable operational readiness; no impersonated certification."""
    return {'simulationBaseUrl':'https://'+SIM_HOST,'legacyProductionSimEndpointDeprecatedByThisPath':True,
            'allFuturesV3DocumentedOnDedicatedSimulationHost':True,
            'simulationCredentialsVerified':False,
            'simulationAccountIsolationVerified':False,
            'closeOnlyExitCertified':False,
            'tpLimitAndStopLossCoexistenceCertified':False,
            'simulatedOrdersSubmitted':False,'liveOrdersSubmitted':False,
            'simulationWritesAllowed':False,'liveWritesAllowed':False,
            'recommendation':'GET-only verification with separate simulation credentials before any order'}
