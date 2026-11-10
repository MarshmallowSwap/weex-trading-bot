"""WEEX LIVE Guardian go/no-go: independent fail-closed READ-ONLY gate.

NEVER sends orders. Does not change live mode. The demo-only partial
replacement engine MUST NOT be enabled merely because its tests pass.
Existing manual or unattributed exposure, SL-off configuration, unresolved
lifecycle writes, insufficient provenance, or stale account proof all veto
new live positions. This gate cannot itself authorize trading.
"""
import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path

def _fresh(iso,max_age=120,now=None):
 try:
  ts=datetime.fromisoformat(iso.replace('Z','+00:00')).timestamp()
  now=datetime.now(timezone.utc).timestamp() if now is None else now
  return 0<=now-ts<=max_age
 except (ValueError,TypeError,AttributeError):return False

def evaluate(config,mode,latest_worker,reconciliation,release,*,current_positions=None,
             current_open_algos=None,positions_bound_to_bot=False,now=None):
 issues=[]
 if mode!='STOPPED':issues.append('LIVE_SWITCH_NOT_STOPPED_DURING_PREFLIGHT')
 if config.get('execution',{}).get('enabled') is True:
  issues.append('EXECUTION_ALREADY_ENABLED')
 from weex_optional_stop_policy import assess as optional_stop
 stop=optional_stop(config)
 if stop.get('valid') is not True:
  issues.append('INCONSISTENT_OPTIONAL_SL_SETTINGS')
 if config.get('risk',{}).get('marginModePreference')=='cross':
  issues.append('CROSS_MARGIN_SHARED_COLLATERAL_RISK')
 if latest_worker.get('status') in ('BLOCKED_RECOVERY','BLOCKED_AFTER_ENTRY',
                                    'BLOCKED_AFTER_DISPATCH','BLOCKED'):
  issues.append('WORKER_HAS_UNRESOLVED_RECOVERY')
 if latest_worker.get('recoveryClear') is not True:
  issues.append('RECOVERY_NOT_CERTIFIED')
 if release.get('gate')!='GO':issues.append('RELEASE_GATE_NOT_GO')
 if not _fresh(release.get('checkedAt'),120,now):issues.append('RELEASE_GATE_STALE')
 if not _fresh(reconciliation.get('checkedAt'),120,now):
  issues.append('ACCOUNT_RECONCILIATION_STALE')
 if reconciliation.get('writes') is not False or reconciliation.get('liveGo') is not False:
  issues.append('UNEXPECTED_RECONCILIATION_MODE')
 if current_positions is None or not isinstance(current_positions,list):
  issues.append('CURRENT_POSITIONS_NOT_VERIFIED')
 elif current_positions and positions_bound_to_bot is not True:
  issues.append('EXISTING_POSITIONS_NOT_BOT_ATTRIBUTED')
 if current_open_algos is None or not isinstance(current_open_algos,list):
  issues.append('CURRENT_PROTECTION_SNAPSHOT_MISSING')
 # A matching TP or SL on the same symbol is NOT identity proof.
 # Manual/external orders must remain untouched.
 if current_open_algos and not positions_bound_to_bot:
  issues.append('UNATTRIBUTED_EXIT_ORDERS_REQUIRE_REVIEW')
 # Never grant authorization through this gate alone.
 return {'state':'LIVE_BLOCKED' if issues else 'PREFLIGHT_ONLY_NO_TRADE_AUTHORIZATION',
         'checks':sorted(set(issues)), 'liveOrdersSent':0,
         'newEntriesPermitted':False,'autoAdoptManualPositions':False,
         'riskOfLoss':'HIGH','demoEngineLiveCapable':False}

def current_state(root,*,position_count=None,algo_count=None,position_ownership=False):
 root=Path(root)
 def load(name):
  try:return json.loads((root/name).read_text(encoding='utf-8'))
  except (OSError,ValueError):return {}
 from live_control import state
 switch=state(root)
 config=load('weex_ai_risk_config.json')
 worker=load('weex_live_worker_latest.json')
 reconciliation=load('official_sdk_live_reconciliation_latest.json')
 release=load('live_release_gate_latest.json')
 # Metadata-only counts do not certify identity; no account write.
 positions=[{} for _ in range(position_count)] if isinstance(position_count,int) and position_count>=0 else None
 algos=[{} for _ in range(algo_count)] if isinstance(algo_count,int) and algo_count>=0 else None
 return evaluate(config,switch['mode'],worker,reconciliation,release,
   current_positions=positions,current_open_algos=algos,
   positions_bound_to_bot=position_ownership)
if __name__=='__main__':
 root=Path(__file__).resolve().parent
 # Live SDK reconciliation returns count, not verified ownership: pass count only.
 data=json.loads((root/'official_sdk_live_reconciliation_latest.json').read_text(encoding='utf-8'))
 print(json.dumps(current_state(root,position_count=data.get('positions'))))
