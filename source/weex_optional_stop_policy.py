"""Optional WEEX stop-loss policy: validates consistency, not trade permission.

User choice: SL may be OFF. Does not waive attribution, TP readback,
unresolved-write protection, exchange fee/funding reconciliation, risk or
release checks. Explicitly exposes liquidation risk with cross/high leverage.
No exchange requests.
"""
def assess(cfg):
    if not isinstance(cfg,dict):return {'valid':False,'reason':'INVALID_CONFIG'}
    risk=cfg.get('risk') or {};s=risk.get('stopLoss') or {}
    settings=cfg.get('strategySettings') or {};execution=cfg.get('execution') or {}
    enabled=s.get('enabled');mode=settings.get('slMode')
    allows=execution.get('allowOrdersWithoutStop')
    if enabled is False and mode=='off' and allows is True:
        return {'valid':True,'stopMode':'OPTIONAL_DISABLED_BY_USER',
                'stopOrderRequired':False,'stopProtectionPresent':False,
                'risk':'UNLIMITED_DIRECTIONAL_LOSS_UP_TO_MARGIN_AND_CROSS_COLLATERAL',
                'canAuthorizeLive':False}
    if enabled is True and mode not in ('off',None) and allows is False:
        return {'valid':True,'stopMode':'ENABLED_REQUIRES_EXCHANGE_READBACK',
                'stopOrderRequired':True,'stopProtectionPresent':False,
                'risk':'STOP_FILL_NOT_GUARANTEED','canAuthorizeLive':False}
    return {'valid':False,'reason':'INCONSISTENT_OPTIONAL_SL_SETTINGS',
            'stopOrderRequired':False,'canAuthorizeLive':False}
