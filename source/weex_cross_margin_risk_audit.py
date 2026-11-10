"""Conservative cross-margin risk audit for the bot-only WEEX account.

The exact financial exposure cannot be bounded by initial position margin in
cross mode. With no SL, a configured number of positions does not define a
guaranteed maximum loss; full shared collateral may be affected. Read-only.
"""
from decimal import Decimal,InvalidOperation
from pathlib import Path
import json
import live_control

def audit(root=None):
 root=Path(root or Path(__file__).resolve().parent)
 cfg,_=live_control.configuration(root)
 risk=cfg['risk'];settings=cfg['strategySettings']
 mode=risk.get('marginModePreference')
 stop_on=bool(risk.get('stopLoss',{}).get('enabled'))
 maxp=cfg['telegramSettings']['maxConcurrentPositions']['default']
 minlev=risk.get('minimumLeverage')
 cost=risk.get('orderCostTargetUSDT')
 equity_budget=None
 # Do not mistake planned order cost or margin for independently collateralized
 # loss limits. A value for account equity is intentionally not fabricated.
 issues=[]
 if mode=='cross':
  issues.append('CROSS_COLLATERAL_SHARED_ACROSS_POSITIONS')
  if not stop_on:issues.append('NO_STOP_CAN_LOSE_SHARED_ACCOUNT_COLLATERAL')
 if mode=='cross' and int(maxp)>1:issues.append('MULTIPLE_CROSS_POSITIONS_COMPOUND_RISK')
 if mode=='cross' and Decimal(str(minlev))>=125:
  issues.append('HIGH_MINIMUM_LEVERAGE_IN_CROSS_MODE')
 if mode=='cross' and cfg.get('execution',{}).get('allowOrdersWithoutStop') is True:
  issues.append('UNBOUNDED_POSITION_LOSS_BEFORE_ACCOUNT_EQUITY')
 return {'scope':'RISK_STRUCTURE_ONLY','marginMode':mode,'stopLossEnabled':stop_on,
  'configuredMaxConcurrentPositions':maxp,
  'configuredMinimumLeverage':str(minlev),
  'configuredOrderCostTargetUSDT':str(cost),
  'configuredInitialMarginTargetUSDT':str(risk.get('initialMarginTargetUSDT')),
  'accountEquityNotAssumed':True,'independentCollateralForEachPosition':False if mode=='cross' else None,
  'positionLossLimitGuaranteedByMargin':False if mode=='cross' else None,
  'lossCeilingCertified':False,'issues':issues,
  'canClearCrossGuardianBlock':False,
  'canEnableLive':False,'exchangeWrites':0}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
