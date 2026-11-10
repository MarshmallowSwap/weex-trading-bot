"""WEEX end-of-work evidence report, does not authorize production trading."""
import json,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
def rd(f):return json.loads((R/f).read_text(encoding='utf-8'))
acct=rd('weex_income_ledger_arithmetic_certification_20261109.json')
trade=rd('weex_cross_live_pilot_certification_20261109.json')
crash=rd('weex_cross_crash_write_boundary_test_20261109.json')
gate=rd('live_release_gate_latest.json')
x={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'project':'WEEX',
 'completedAndCertified':{
  'ETHUSDT_real_CROSS_1x_single_order_lifecycle':trade['livePilotCycleCertified'],
  'native_attached_stop_and_exact_position_close':trade['livePilotStopTerminalCertified'] and trade['livePilotExactPositionCloseCertified'],
  'account_USDT_ledger_1335_records_bounded_window':acct['boundedLedgerAccountingCertified'],
  '1000_fill_identity_matches':acct['all1000FillsLinkedToBills'],
  'simulated_entry_and_close_crash_no_duplicates':crash['allSimulatedWriteBoundaryChecksPassed']},
 'unresolvedGlobalReleaseItems':[
  'historical_quote_amounts_reconciled: original general gate requires different full historical accounting policy; scoped ledger certified only',
  'crash_restart_recovery_live_tested: no active REAL order crash interrupted; simulated boundary test alone is not equivalent'],
 'latestGeneralGate':gate['gate'],
 'latestPassedChecks':gate['passed'],'latestTotalChecks':gate['total'],
 'mainBotMode':live_control.state(R)['mode'],
 'integrityErrors':live_control.build_errors(R),
 'orderExecutionAuthorized':False,'newOrdersPlacedByConclusion':0,
 'releaseGateManipulated':False,'botRestarted':False,
 'evidence':['weex_income_ledger_arithmetic_certification_20261109.json',
 'weex_cross_live_pilot_certification_20261109.json',
 'weex_cross_crash_write_boundary_test_20261109.json',
 'weex_1000_fill_income_liquidation_classification_20261109.json']}
o=R/'weex_FINAL_RELEASE_EVIDENCE_20261109.json'
t=o.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');os.replace(t,o)
print(json.dumps(x))
