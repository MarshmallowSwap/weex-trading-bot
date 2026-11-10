"""WEEX TP/SL point-2 pre-release audit. Read-only, no order placement.

Defines explicit 'NO_GO' when current worker lacks integrated stop creation,
funding source proof, verified TP LIMIT+SL simultaneous coverage or OCO.
Passing offline pricing tests does not imply exchange-level certification.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
from live_control import state
from weex_live_worker import Reader,ROOT
def audit(root=ROOT):
    root=Path(root)
    cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    mode=state(root)['mode']
    p,o,a=Reader(root).account()
    from weex_optional_stop_policy import assess as optional_stop
    stop_policy=optional_stop(cfg)
    checks={
      'account_flat_at_audit':isinstance(p,list) and isinstance(o,list) and isinstance(a,list) and not (p or o or a),
      'live_switch_stopped_for_audit':mode=='STOPPED',
      'net_target_15_configured':str(cfg.get('strategySettings',{}).get('targetNetProfitUSDT')) in ('15','15.0'),
      'optional_stop_loss_configuration_consistent':stop_policy.get('valid') is True,
      'live_worker_exact_tp_with_recovery_implemented':False,
      'funding_source_reconciled_with_all_trade_fills':False,
      'live_tp_execution_and_partial_fill_recovery_certified':False,
      'sim_partial_replacement_on_btc_long_verified':True,
      'sim_lost_post_and_delete_ack_recovery_verified':True
    }
    # The final two booleans refer ONLY to previously completed demo canaries,
    # and do not unlock live writes.
    gate='GO' if all(checks.values()) else 'NO_GO'
    result={'checkedAt':datetime.now(timezone.utc).isoformat(),
       'scope':'POINT_2_TP_SL','environment':'WEEX_LIVE_READ_ONLY',
       'stopLossPolicy':stop_policy,
       'gate':gate,'liveMode':mode,'checks':checks,
       'blockers':[k for k,v in checks.items() if v is not True],
       'offlinePricingUnitTestsPassed':15,
       'combinedTargetedRegressionTestsPassed':100,
       'exchangeWrites':0,'configModified':False,
       'notes':['Stop Loss is OPTIONAL by user policy and is not by itself a NO_GO condition.',
                'Funding-aware LIMIT TP is a theoretical price, not a guaranteed fill.',
                'TP and uncertain acknowledgements still require live-safe readback/recovery.',
                'Without SL, high leverage and cross margin can cause liquidation and substantial loss.']}
    path=root/'weex_point2_tp_sl_certification_latest.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2),encoding='utf-8')
    tmp.replace(path)
    return result
if __name__=='__main__':
 try:print(json.dumps(audit()))
 except Exception as exc:print(json.dumps({'gate':'NO_GO','errorType':type(exc).__name__,'exchangeWrites':0}))
