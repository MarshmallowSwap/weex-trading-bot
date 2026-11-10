"""Read-only operational reconciliation from fresh account and local journals."""
import json,sqlite3,time
from datetime import datetime,timezone
from pathlib import Path
from weex_capacity import account_capacity,lifecycle_position_ids
R=Path(__file__).resolve().parent
def load(name):
    return json.loads((R/name).read_text(encoding="utf-8"))
def age(stamp):
    return time.time()-datetime.fromisoformat(str(stamp).replace("Z","+00:00")).timestamp()
account=load("weex_account_observation_latest.json")
cover=load("position_manager_integrated_latest.json")
fills=load("live_recent_fill_reconciliation_latest.json")
positions=account.get("positions",[])
regular=account.get("regularOrders",[])
conditional=account.get("conditionalOrders",[])
trailing=account.get("trailingOrders",[])
trade_db=R/"weex_user_live_lifecycle.sqlite3"
c=sqlite3.connect(f"file:{trade_db.as_posix()}?mode=ro",uri=True);c.execute("PRAGMA query_only=ON")
rows=c.execute("SELECT id,symbol,state,owned,plan FROM trades_v1").fetchall()
pending_writes=c.execute("""SELECT COUNT(*) FROM writes_v1 w JOIN trades_v1 t ON t.id=w.trade_id
 WHERE t.state NOT IN ('CLOSED','REJECTED','SUPERSEDED') AND w.state NOT IN ('RESPONSE_RECEIVED','ACKNOWLEDGED')""").fetchone()[0]
c.close()
managed_ids=lifecycle_position_ids(trade_db)
if managed_ids is None:raise RuntimeError("LIFECYCLE_LEDGER_UNREADABLE")
active=[r for r in rows if str(r[2]).upper() not in ("CLOSED","REJECTED","SUPERSEDED")]
active_position_ids=set()
for r in active:
    owned=json.loads(r[3] or "{}")
    plan=json.loads(r[4] or "{}")
    source=owned.get("entrySource",plan.get("entrySource","automatic"))
    if source!="manual_telegram" and owned.get("positionId") is not None:
        active_position_ids.add(str(owned["positionId"]))
capacity=account_capacity(positions,regular+conditional+trailing,managed_ids)
intent_db=R/"execution_intents.sqlite3"
c=sqlite3.connect(f"file:{intent_db.as_posix()}?mode=ro",uri=True);c.execute("PRAGMA query_only=ON")
intent_states=c.execute("SELECT state,COUNT(*) FROM intents GROUP BY state").fetchall()
intent_count=c.execute("SELECT COUNT(*) FROM intents").fetchone()[0]
bindings=c.execute("SELECT COUNT(*) FROM client_bindings").fetchone()[0]
c.close()
position_ids={str(p.get("id")) for p in positions}
active_reconciled=all(str(r[2]).upper()=="PROTECTED" for r in active) and active_position_ids.issubset(position_ids)
checks={
 "fresh_complete_account":account.get("complete") is True and 0<=age(account.get("observedAt",""))<=120,
 "position_snapshot_matches":cover.get("asOf")==account.get("observedAt"),
 "all_current_positions_have_verified_tp":cover.get("coverageCertified") is True and len(cover.get("items",[]))==len(positions) and all(x.get("coverage",{}).get("verified") is True and x.get("coverage",{}).get("tpCovered") is True for x in cover.get("items",[])),
 "lifecycle_recovery_clear":active_reconciled and pending_writes==0,
 "no_bot_owned_open_capacity":capacity.get("count")==0,
 "manual_positions_excluded_consistently":capacity.get("manualPositionsExcluded")==len(positions)-len(active_position_ids),
 "no_unresolved_local_intents":intent_count==0 and bindings==0 and not intent_states,
 "recent_trade_rows_bound_to_exact_orders":0<=age(fills.get("checkedAt",""))<=300 and 0<=age(fills.get("sourceCheckedAt",""))<=300 and fills.get("recentMissingOrderFillIdentityResolved") is True and int(fills.get("sourceMatchedToHistory",0))+int(fills.get("sourceMissingRows",0))==int(fills.get("sourceTradeRows",0))
}
cert=all(checks.values())
result={
 "checkedAt":datetime.now(timezone.utc).isoformat(),"currentAccountObservedAt":account.get("observedAt"),
 "scope":"Fresh account positions and orders, TP coverage, local bot lifecycle/intents, and latest bounded trade snapshot.",
 "status":"OPERATIONAL_RECONCILIATION_CLEAR" if cert else "RECONCILIATION_INCOMPLETE",
 "operationalReconciliationCertified":cert,"checks":checks,
 "currentPositions":[{"symbol":p.get("symbol"),"side":p.get("side"),"size":p.get("size"),"leverage":p.get("leverage")} for p in positions],
 "openOrders":{"regular":len(regular),"conditional":len(conditional),"trailing":len(trailing)},
 "capacity":capacity,"botLifecycle":{"records":len(rows),"states":[{"symbol":x[1],"state":x[2]} for x in rows],"activeRecords":len(active),"pendingWrites":pending_writes},
 "localIntents":{"count":intent_count,"states":intent_states,"clientBindings":bindings},
 "recentFillReconciliation":{"checkedAt":fills.get("checkedAt"),"tradeRows":fills.get("sourceTradeRows"),"historyMatches":fills.get("sourceMatchedToHistory"),"exactOrderIdResolutions":fills.get("sourceMissingRows"),"distinctOrders":fills.get("distinctMissingOrders"),"identityResolved":fills.get("recentMissingOrderFillIdentityResolved")},
 "financialQuoteAudit":fills.get("financialQuoteReconciliation"),
 "fullHistoricalCoverage":False,"ownershipInferred":False,"exchangeWrites":False,"telegramMessagesSent":False,
 "limitation":"Operational state only; historical quote variances and history outside the latest bounded trade snapshot remain unaudited."
}
target=R/"account_reconciliation_point1_latest.json";tmp=target.with_suffix(".tmp")
tmp.write_text(json.dumps(result,indent=2),encoding="utf-8");tmp.replace(target)
print(json.dumps({"status":result["status"],"checks":checks,"capacity":capacity,"exchangeWrites":False},ensure_ascii=False))
