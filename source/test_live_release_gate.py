import unittest
from datetime import datetime,timezone,timedelta
from live_release_gate import (RECON_CHECKS,recent_operational_reconciliation,
    certified_book_subset,evaluate_historical_execution)

def valid_report(now):
    return {"checkedAt":now.isoformat(),"currentAccountObservedAt":now.isoformat(),
      "status":"OPERATIONAL_RECONCILIATION_CLEAR","operationalReconciliationCertified":True,
      "checks":{k:True for k in RECON_CHECKS},"fullHistoricalCoverage":False,
      "ownershipInferred":False,"exchangeWrites":False,"telegramMessagesSent":False,
      "financialQuoteAudit":"INCOMPLETE"}

def history_fixture():
    trade={"id":"t1","symbol":"ETHUSDT","state":"CLOSED",
      "plan":'{"entrySource":"automatic","requestedLeverage":"125","publicRiskTierVerified":true,"entry":{"newClientOrderId":"wxentry_t1"}}',
      "owned":'{"entryOrderId":"1"}'}
    writes=[{"trade_id":"t1","kind":"ENTRY","state":"RESPONSE_RECEIVED",
      "response":'{"success":true,"orderId":"1","clientOrderId":"wxentry_t1"}'},
      {"trade_id":"t1","kind":"TP","state":"RESPONSE_RECEIVED","response":'[{"success":true,"orderId":"2"}]'}]
    quality={"checkedAt":datetime.now(timezone.utc).isoformat(),"mode":"READ_ONLY_LOCAL","networkRequests":0,"exchangeWrites":0,"trades":[{
      "tradeId":"t1","symbol":"ETHUSDT","verifiedLeverage":"125","tpOwner":"BOT",
      "tpAcknowledged":True,"exitEvidence":"RECONCILED_LEDGER","targetMetBeforeFunding":True}]}
    return [trade],writes,quality

class OperationalReconciliationGateTests(unittest.TestCase):
    def test_fresh_operational_state_passes_with_explicit_history_scope(self):
        now=datetime.now(timezone.utc)
        self.assertTrue(recent_operational_reconciliation(valid_report(now),now.timestamp()))
    def test_financial_quote_audit_does_not_clear_or_block_open_state(self):
        now=datetime.now(timezone.utc);r=valid_report(now);r["financialQuoteAudit"]="INCOMPLETE"
        self.assertTrue(recent_operational_reconciliation(r,now.timestamp()))
    def test_stale_account_snapshot_fails(self):
        now=datetime.now(timezone.utc);r=valid_report(now)
        r["currentAccountObservedAt"]=(now-timedelta(seconds=121)).isoformat()
        self.assertFalse(recent_operational_reconciliation(r,now.timestamp()))
    def test_missing_required_proof_fails(self):
        now=datetime.now(timezone.utc);r=valid_report(now);r["checks"]["no_unresolved_local_intents"]=False
        self.assertFalse(recent_operational_reconciliation(r,now.timestamp()))
    def test_claim_of_full_history_or_side_effects_fails(self):
        now=datetime.now(timezone.utc);r=valid_report(now);r["fullHistoricalCoverage"]=True
        self.assertFalse(recent_operational_reconciliation(r,now.timestamp()))
        r=valid_report(now);r["exchangeWrites"]=True
        self.assertFalse(recent_operational_reconciliation(r,now.timestamp()))
    def test_partial_but_enforced_book_scope_passes(self):
        m={"state":"PARTIAL_COVERAGE","verifiedSymbols":["BTCUSDT","ETHUSDT"],"unitsVerified":2,"liquidityPassed":2}
        self.assertTrue(certified_book_subset(m));m["unitsVerified"]=1
        self.assertFalse(certified_book_subset(m))
    def test_real_historical_adapter_tp_and_leverage_evidence(self):
        t,w,q=history_fixture();r=evaluate_historical_execution(t,w,q,125)
        self.assertTrue(r["liveAdapterTested"]);self.assertTrue(r["tpExchangeTested"])
        self.assertTrue(r["historicalLeverageTiersVerified"])
    def test_wrong_client_order_id_fails_adapter(self):
        t,w,q=history_fixture();w[0]["response"]='{"success":true,"orderId":"1","clientOrderId":"wrong"}'
        self.assertFalse(evaluate_historical_execution(t,w,q,125)["liveAdapterTested"])
    def test_no_tp_close_evidence_fails_tp_gate(self):
        t,w,q=history_fixture();q["trades"][0]["exitEvidence"]="NOT_AVAILABLE"
        self.assertFalse(evaluate_historical_execution(t,w,q,125)["tpExchangeTested"])

if __name__=="__main__":unittest.main()
