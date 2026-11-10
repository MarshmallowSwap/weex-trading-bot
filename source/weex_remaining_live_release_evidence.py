"""Immutable-evidence release blockers report (NO changes to live gate).
Separates the bounded snapshot accounting proof, the unresolved WEEX
parent-field contradictions, and localhost lost-ACK vs live-crash evidence.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
def get(n):return json.loads((R/n).read_text(encoding='utf-8'))
summary=get('weex_1000_fill_economics_consolidated.json')
distribution=get('weex_1000_parent_quote_mismatch_full_audit.json')
singles=get('weex_1000_three_single_fill_parent_quote_readback.json')
decision=get('live_release_gate_latest.json')
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'productionMode':live_control.state(R)['mode'],
 'productionIntegrity':live_control.build_errors(R),
 'decision':decision['gate'],'gatePassed':decision['passed'],'gateTotal':decision['total'],
 'accounting':{'filledSnapshotRows':summary['fillsIndividuallyVerified'],
  'orders':summary['ordersWithExactExchangeIdentity'],
  'allSnapshotFillAmountsReconciled':summary['allOrdersFillBasedNotionalAndFeesReconciled'],
  'parentFieldsDisagreeWithFills':summary['parentCumQuoteDiscrepancyTotalOrders'],
  'multiPriceFilledDiscrepancies':distribution['filledMismatchMultiplePrices'],
  'singlePriceFilledDiscrepancies':distribution['filledMismatchSinglePrice'],
  'singlePriceReadbackVerified':singles['parentFieldsConflicting'],
  'fullHistoryCertified':summary['fullAccountHistoryCovered'],
  'parentFieldsSemanticsCertified':summary['weexParentFieldSemanticsResolved']},
 'crashRecovery':{'localhostLostHttpResponseRegressionPassedInTestSuite':True,
  'actualProductionPostInterruptedAndReconciled':False,
  'liveCrashGateSatisfied':False},
 'requiredEvidenceForHistoricalQuoteGate':[
  'Explicit, reproducible acceptance of fill-derived economic notional for a precisely bounded scope',
  'Independent corroboration or official WEEX clarification of parent cumQuote/avgPrice semantics',
  'Define historical coverage and reconcile funding/fees before claiming full account PnL'],
 'requiredEvidenceForCrashRestartLiveGate':[
  'Controlled, preapproved real-exchange interrupted write with durable intent and exact order ID',
  'Independent post-restart account, order, fills, protective stop and close readback',
  'Proof no duplicate submission and no unprotected residual position'],
 'manualOverrideApplied':False,'releaseGateModified':False,
 'ordersSubmitted':0}
p=R/'weex_remaining_live_release_evidence.json'
t=p.with_suffix('.tmp');t.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(t,p)
print(json.dumps({k:v for k,v in report.items() if k not in ('requiredEvidenceForHistoricalQuoteGate','requiredEvidenceForCrashRestartLiveGate')}))
