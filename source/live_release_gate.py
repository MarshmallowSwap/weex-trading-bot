"""WEEX release gate: evidence-scoped, read-only; never submits orders."""
import json,sqlite3
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
from contextlib import closing
from agent_health import assess,assess_agents
ROOT=Path(__file__).resolve().parent
RECON_CHECKS=(
 "fresh_complete_account","position_snapshot_matches",
 "all_current_positions_have_verified_tp","lifecycle_recovery_clear",
 "no_bot_owned_open_capacity","manual_positions_excluded_consistently",
 "no_unresolved_local_intents","recent_trade_rows_bound_to_exact_orders",
)
def read(name,root=ROOT):
 try:return json.loads((Path(root)/name).read_text(encoding="utf-8"))
 except Exception:return {}
def recent_operational_reconciliation(report,now=None,max_age_seconds=120):
 """Certify only fresh account/recovery state; never imply full history coverage."""
 try:
  now=datetime.now(timezone.utc).timestamp() if now is None else now
  checked=datetime.fromisoformat(str(report["checkedAt"]).replace("Z","+00:00")).timestamp()
  account_stamp=report.get("currentAccountObservedAt") or report.get("accountObservedAt")
  account=datetime.fromisoformat(str(account_stamp).replace("Z","+00:00")).timestamp()
  checks=report["checks"]
  recent=0<=now-checked<=max_age_seconds and 0<=now-account<=max_age_seconds
  return (recent and report.get("status")=="OPERATIONAL_RECONCILIATION_CLEAR"
    and report.get("operationalReconciliationCertified") is True
    and all(checks.get(k) is True for k in RECON_CHECKS)
    and report.get("fullHistoricalCoverage") is False
    and report.get("ownershipInferred") is False
    and report.get("exchangeWrites") is False
    and report.get("telegramMessagesSent") is False)
 except (KeyError,TypeError,ValueError,AttributeError):return False
def certified_book_subset(module):
 symbols=module.get("verifiedSymbols")
 return (module.get("state") in ("PARTIAL_COVERAGE","READY_ANALYSIS")
  and isinstance(symbols,list) and bool(symbols) and len(set(symbols))==len(symbols)
  and module.get("unitsVerified")==len(symbols)
  and module.get("liquidityPassed")==len(symbols))
def evaluate_historical_execution(trades,writes,quality,min_leverage=125):
 """Check recorded real lifecycle acknowledgements without claiming global availability."""
 try:
  qrows={x["tradeId"]:x for x in quality.get("trades",[]) if isinstance(x,dict) and x.get("tradeId")}
  by_trade={}
  for w in writes:by_trade.setdefault(w["trade_id"],{})[w["kind"]]=w
  entries=[];tiers=[];tp_closed=[]
  for t in trades:
   tid=t["id"];plan=json.loads(t["plan"] or "{}");owned=json.loads(t["owned"] or "{}")
   if plan.get("entrySource")=="manual_telegram":continue
   response=by_trade.get(tid,{}).get("ENTRY",{})
   raw=json.loads(response.get("response") or "{}")
   expected=plan.get("entry",{}).get("newClientOrderId")
   entry_ok=(response.get("state")=="RESPONSE_RECEIVED" and raw.get("success") is True
     and bool(raw.get("orderId")) and raw.get("clientOrderId")==expected and bool(expected))
   if owned.get("entryOrderId") is not None:
    entry_ok=entry_ok and str(owned["entryOrderId"])==str(raw.get("orderId"))
   if entry_ok:entries.append(tid)
   q=qrows.get(tid,{})
   try:
    requested=Decimal(str(plan.get("requestedLeverage")))
    verified=Decimal(str(q.get("verifiedLeverage")))
    tier_ok=(plan.get("publicRiskTierVerified") is True and requested>=Decimal(str(min_leverage))
      and verified>=Decimal(str(min_leverage)))
   except (InvalidOperation,TypeError,ValueError):tier_ok=False
   if tier_ok:tiers.append(tid)
   tpw=by_trade.get(tid,{}).get("TP",{})
   try:tpraw=json.loads(tpw.get("response") or "[]")
   except (ValueError,TypeError):tpraw=[]
   tp_ack=(tpw.get("state")=="RESPONSE_RECEIVED" and isinstance(tpraw,list) and len(tpraw)==1
      and tpraw[0].get("success") is True and bool(tpraw[0].get("orderId")))
   if (tp_ack and q.get("tpOwner")=="BOT" and q.get("tpAcknowledged") is True
       and q.get("exitEvidence")=="RECONCILED_LEDGER" and q.get("targetMetBeforeFunding") is True):
    tp_closed.append(tid)
  expected_trades=[t for t in trades if json.loads(t["plan"] or "{}").get("entrySource")!="manual_telegram"]
  quality_at=datetime.fromisoformat(str(quality["checkedAt"]).replace("Z","+00:00")).timestamp()
  quality_fresh=(0<=datetime.now(timezone.utc).timestamp()-quality_at<=900
    and quality.get("mode")=="READ_ONLY_LOCAL" and quality.get("networkRequests")==0
    and quality.get("exchangeWrites")==0 and bool(qrows))
  return {"liveAdapterTested":quality_fresh and bool(expected_trades) and len(entries)==len(expected_trades),
   "tpExchangeTested":quality_fresh and bool(tp_closed),
   "historicalLeverageTiersVerified":quality_fresh and bool(expected_trades) and len(tiers)==len(expected_trades),
   "entryAcknowledgements":len(entries),"botTradeRecords":len(expected_trades),
   "closedBotTpEvidence":len(tp_closed),"leverageTierEvidence":len(tiers),
   "verifiedSymbols":sorted({qrows[t]["symbol"] for t in tiers if t in qrows})}
 except (KeyError,TypeError,ValueError,sqlite3.Error):
  return {"liveAdapterTested":False,"tpExchangeTested":False,
   "historicalLeverageTiersVerified":False,"entryAcknowledgements":0,
   "botTradeRecords":0,"closedBotTpEvidence":0,"leverageTierEvidence":0,"verifiedSymbols":[]}
def historical_execution(root=ROOT,min_leverage=125):
 root=Path(root)
 try:
  db=root/"weex_user_live_lifecycle.sqlite3"
  with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro",uri=True)) as c:
   c.row_factory=sqlite3.Row;c.execute("PRAGMA query_only=ON")
   trades=[dict(x) for x in c.execute("SELECT id,symbol,state,plan,owned FROM trades_v1")]
   writes=[dict(x) for x in c.execute("SELECT trade_id,kind,state,response FROM writes_v1")]
  return evaluate_historical_execution(trades,writes,read("weex_closed_quality_latest.json",root),min_leverage)
 except (OSError,sqlite3.Error):return evaluate_historical_execution([],[],{},min_leverage)
def bounded_income_accounting_certified(ledger,classification,join):
 """Accept only authenticated, complete BOUNDED execution income evidence.

 Does not claim full account lifetime or resolve exchange parent cumQuote.
 Liquidation corrections are recorded in exchange income and balanced, but
 are not misrepresented as ordinary per-fill commission.
 """
 try:
  chain=ledger['balanceArithmetic']
  return (ledger.get('scope')=='WEEX_ACCOUNT_USDT_LEDGER_IN_EXHAUSTED_BOUNDED_WINDOW'
   and ledger.get('ledgerWindowComplete') is True
   and ledger.get('boundedLedgerAccountingCertified') is True
   and ledger.get('all1000FillsLinkedToBills') is True
   and ledger.get('997OrdinaryFillsQuoteAndFeeMatch') is True
   and ledger.get('3LiquidationsPresentInAuthoritativeBillLedger') is True
   and chain.get('verified') is True and chain.get('billCount')==1335
   and chain.get('transitionsChecked')==1334 and chain.get('gaps')==[]
   and Decimal(str(chain['sumMovementUSDT']))==Decimal(str(chain['firstToLastBalanceDeltaUSDT']))
   and ledger.get('entireAccountLifetimeCertified') is False
   and ledger.get('productionGateChanged') is False
   and ledger.get('newExchangeWrites')==0
   and classification.get('scope')=='1000_FIXED_AUTHENTICATED_FILLS_WITH_FULL_PAGED_INCOME_WINDOW'
   and classification.get('incomeWindowComplete') is True
   and classification.get('fillsLinkedOneToOneWithIncomeBill')==1000
   and classification.get('ordinaryFillExactIncomeMatches')==997
   and classification.get('liquidationAdjustmentFillCount')==3
   and classification.get('liquidationEventTimingExplainsClass') is True
   and classification.get('allFillsAttributedToEitherExactOrdinaryBillOrLiquidation') is True
   and classification.get('parentCumQuoteCanBeUsedAsAccountingSource') is False
   and classification.get('fullAccountLifetimeEconomicsCertified') is False
   and join.get('snapshotFills')==1000
   and join.get('matchedUniqueFillToBillCount')==1000
   and join.get('unmatchedFillCount')==0
   and join.get('ambiguousFillCount')==0
   and join.get('exactQuoteAndFeeDeltaCount')==997
   and join.get('all1000DirectBillsMatched') is True
   and join.get('releaseGateChanged') is False
   and join.get('exchangeWrites')==0)
 except (KeyError,ValueError,TypeError,InvalidOperation,ArithmeticError):
  return False

def check():
 from weex_real_worker_crash_evidence_gate import certify as crash_evidence
 real_crash=crash_evidence(ROOT)
 cfg=read("weex_ai_risk_config.json")
 pos=read("position_manager_integrated_latest.json")
 health=assess()
 readiness=assess_agents()
 reconciliation=read("account_reconciliation_point1_latest.json")
 liquidity=readiness["modules"]["liquidity"]
 execution=historical_execution()
 book_ok=certified_book_subset(liquidity)
 tp_policy=cfg.get("risk",{}).get("stopLoss",{}).get("enabled") is False
 checks={
  "market_heartbeat_recent":health.get("status")=="OK",
  "contract_book_unit_certified_for_subset":book_ok,
  "order_reconciliation_certified":recent_operational_reconciliation(reconciliation),
  "bounded_execution_income_accounting_verified":bounded_income_accounting_certified(
      read("weex_income_ledger_arithmetic_certification_20261109.json"),
      read("weex_1000_fill_income_liquidation_classification_20261109.json"),
      read("weex_fill_income_ledger_join_20261109.json")),
  "protective_order_coverage_certified":pos.get("coverageCertified") is True,
  "tp_exchange_exit_verified_sl_off":tp_policy and execution["tpExchangeTested"],
  "live_adapter_tested_from_real_lifecycle":execution["liveAdapterTested"],
  "historical_leverage_tiers_verified_for_traded_symbols":execution["historicalLeverageTiersVerified"],
  "crash_restart_recovery_live_tested":real_crash.get('certified') is True,
  "execution_disabled_during_preflight":cfg.get("execution",{}).get("enabled") is False
 }
 gate="GO" if all(checks.values()) else "NO_GO"
 result={"checkedAt":datetime.now(timezone.utc).isoformat(),"gate":gate,"checks":checks,
  "passed":sum(checks.values()),"total":len(checks),"ordersPlacedByAudit":False,
  "fullHistoricalCoverage":False,
  "evidenceScopes":{
   "book":{"verifiedSymbols":liquidity.get("verifiedSymbols",[]),"scannerAnalyzesBroaderUniverseButRunnerVetoesUnverifiedBooks":True},
   "historicalExecution":execution,
   "reconciliation":"Fresh operational account state and latest bounded trade rows; not complete account history.",
   "sl":"SL is disabled by configuration; only TP placement/exit evidence is assessed.",
   "restart":real_crash
  }}
 result["agentReadiness"]=readiness["modules"]
 (ROOT/"live_release_gate_latest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 return result
if __name__=="__main__":
 x=check();print("LIVE_RELEASE",x["gate"],"checks",x["passed"],"/",x["total"])
 for k,v in x["checks"].items():print("PASS" if v else "BLOCK",k)
