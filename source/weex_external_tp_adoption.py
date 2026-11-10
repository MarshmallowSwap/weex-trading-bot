"""Read-only adoption evidence for manually created WEEX full-position TP.
Never rewrites bot dispatch history or authorizes new entries.
"""
import hashlib
from contextlib import closing
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from weex_capacity import full_closing_tp

def _num(value):
    x = Decimal(str(value))
    if not x.is_finite() or x <= 0:
        raise ValueError("INVALID_POSITIVE_VALUE")
    return x

def verify(root, trade_id, rows, observed_at):
    root = Path(root)
    positions, regular, algos = rows
    if not isinstance(observed_at, int):
        raise ValueError("OBSERVATION_TIMESTAMP_REQUIRED")
    from weex_lifecycle import now
    if not 0 <= now() - observed_at <= 5000:
        raise ValueError("STALE_ACCOUNT_SNAPSHOT")
    with closing(sqlite3.connect(f"file:{(root/'weex_user_live_lifecycle.sqlite3').resolve().as_posix()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        raw = db.execute("SELECT id,symbol,state,owned,plan FROM trades_v1 WHERE id=?", (trade_id,)).fetchone()
        if raw is None or raw["state"] in ("CLOSED","REJECTED","SUPERSEDED"):
            raise ValueError("INVALID_ACTIVE_TRADE")
        trade = dict(raw)
        owned = json.loads(trade["owned"] or "{}")
        plan = json.loads(trade["plan"])
        if not owned or not owned.get("entryOrderId") or not owned.get("positionId"):
            raise ValueError("MISSING_OWNERSHIP_PROOF")
        if plan.get("entrySource") == "manual_telegram":
            raise ValueError("MANUAL_POSITION_NOT_ADOPTABLE")
        if db.execute("SELECT 1 FROM writes_v1 WHERE trade_id=? AND kind='TP'", (trade_id,)).fetchone():
            raise ValueError("BOT_TP_DISPATCH_ALREADY_RECORDED")
        entry = db.execute("SELECT response FROM writes_v1 WHERE trade_id=? AND kind='ENTRY'", (trade_id,)).fetchone()
        if entry is None or not entry[0]:
            raise ValueError("ENTRY_ACK_MISSING")
        ack = json.loads(entry[0])
        if ack.get("success") is not True or str(ack.get("orderId")) != str(owned["entryOrderId"]):
            raise ValueError("ENTRY_ACK_MISMATCH")
    ps = [p for p in positions if p.get("symbol") == trade["symbol"]]
    if len(ps) != 1:
        raise ValueError("POSITION_NOT_UNIQUE")
    p = ps[0]
    if str(p.get("id")) != str(owned["positionId"]) or p.get("side") != plan["entry"]["positionSide"] or _num(p.get("size")) != _num(owned["quantity"]):
        raise ValueError("POSITION_OWNERSHIP_CHANGED")
    if _num(p.get("openValue")) != _num(owned["actualEntryCostUSDT"]) or _num(p.get("openFee")) != _num(owned["actualEntryFeesUSDT"]):
        raise ValueError("ENTRY_ECONOMICS_CHANGED")
    if any(o.get("symbol") == trade["symbol"] for o in regular):
        raise ValueError("OTHER_REGULAR_ORDERS")
    candidates = [a for a in algos if a.get("symbol") == trade["symbol"]]
    if len(candidates) != 1 or not full_closing_tp(candidates[0], ps):
        raise ValueError("NO_UNIQUE_FULL_CLOSING_TP")
    tp = candidates[0]
    if tp.get("orderType") != "TAKE_PROFIT_MARKET" or not tp.get("algoId"):
        raise ValueError("NOT_FIXED_TP")
    if _num(tp.get("triggerPrice")) <= 0:
        raise ValueError("INVALID_TP_PRICE")
    if (p["side"] == "LONG" and _num(tp["triggerPrice"]) <= _num(p["openValue"])/_num(p["size"])) or (p["side"] == "SHORT" and _num(tp["triggerPrice"]) >= _num(p["openValue"])/_num(p["size"])):
        raise ValueError("TP_NOT_PROFITABLE_BEFORE_FEES")
    evidence = {"schema":"EXTERNAL_TP_ADOPTION_EVIDENCE_V1","tradeId":trade_id,"symbol":trade["symbol"],
        "observedAtMs":observed_at,"positionId":str(p["id"]),"entryOrderId":str(owned["entryOrderId"]),
        "positionSide":p["side"],"quantity":str(p["size"]),"algoId":str(tp["algoId"]),
        "triggerPrice":str(tp["triggerPrice"]),"workingType":tp.get("workingType"),
        "reduceOnly":True,"closePosition":tp.get("closePosition"),"origin":"MANUAL_EXTERNAL",
        "strategyTpPrice":owned["tpRequest"]["triggerPrice"],"strategyTpType":owned["tpRequest"]["triggerPriceType"],
        "notBotDispatched":True,"doesNotAuthorizeLive":True}
    payload = json.dumps(evidence,sort_keys=True,separators=(",",":"))
    evidence["sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    return evidence

def save_evidence(root,evidence):
    folder=Path(root)/"weex_external_tp_evidence"
    folder.mkdir(exist_ok=True)
    path=folder/(hashlib.sha256(evidence["tradeId"].encode()).hexdigest()+".json")
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    os.replace(temp,path)
    return str(path)
