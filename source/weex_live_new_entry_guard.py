"""Mandatory WEEX live *new-entry* preflight, no network or orders.

For entry only; does not stop read-only reconciliation/recovery.
Never allow max-leverage cross-margin entry without evidenced protection
or while unrelated/manual positions are active on shared collateral.
"""
from decimal import Decimal, InvalidOperation
from weex_live_position_protection_shadow import assess as coverage
def evaluate(cfg,positions,regular,algos):
 issues=[]
 if not isinstance(cfg,dict):issues.append('CONFIG_INVALID');cfg={}
 risk=cfg.get('risk') or {}
 execution=cfg.get('execution') or {}
 strategy=cfg.get('strategySettings') or {}
 from weex_optional_stop_policy import assess as optional_stop
 stop=optional_stop(cfg)
 if stop.get('valid') is not True:issues.append('INCONSISTENT_OPTIONAL_SL_SETTINGS')
 if cfg.get('environment')!='live_requested_not_enabled':
  issues.append('UNEXPECTED_LIVE_ENVIRONMENT_CONFIG')
 report=coverage(positions,regular,algos)
 if report['status'] in ('SNAPSHOT_INVALID','POSITION_IDENTITY_UNKNOWN'):
  issues.append('ACCOUNT_SNAPSHOT_INVALID')
 elif report['positionCount']:
  # No adoption of existing positions before exact bot provenance proof.
  issues.append('EXISTING_POSITIONS_REQUIRE_SEPARATE_GUARDIAN_OWNERSHIP')
 if isinstance(regular,list) and regular:issues.append('EXISTING_REGULAR_ORDERS')
 if isinstance(algos,list) and algos:issues.append('EXISTING_CONDITIONAL_ORDERS')
 if risk.get('marginModePreference')=='cross':
  # Bounded single-position Cross trial only. A shared Cross balance cannot be
  # treated like isolated collateral. Any current exposure or pending order
  # blocks additional entries; the general multi-position Cross mode remains
  # uncertified. Telegram still requires a fresh explicit LIVE confirmation.
  try:
   cost=Decimal(str(risk['orderCostTargetUSDT']))
   leverage=Decimal(str(risk['minimumLeverage']))
   cap=cfg['telegramSettings']['maxConcurrentPositions']['default']
   scope=(cost.is_finite() and 0<cost<=Decimal('15')
          and leverage.is_finite() and 0<leverage<=Decimal('125')
          and type(cap) is int and 1<=cap<=3
          and risk.get('entryBudgetMode')=='COST_INCLUDING_ENTRY_FEE'
          and execution.get('enabled') is False
          and execution.get('mode')=='PRETRADE'
          and strategy.get('tpMode')=='fixed'
          and strategy.get('tpAccountingMode')=='GROSS_BEFORE_COSTS'
          and Decimal(str(strategy['targetNetProfitUSDT']))==Decimal('30'))
  except (KeyError,TypeError,ValueError,InvalidOperation,AttributeError):
   scope=False
  if not scope or report.get('positionCount')!=0 or regular or algos:
   issues.append('SHARED_CROSS_MARGIN_UNCERTIFIED')
 # This pre-entry veto never authorizes a network write on its own.
 return {'allowed':not issues,'issues':sorted(set(issues)),
         'readOnly':True,'authorizesNetworkWrite':False}
