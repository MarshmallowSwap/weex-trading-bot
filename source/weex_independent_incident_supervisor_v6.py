"""Independent, read-only incident supervisor V6.
Never places/cancels/closes orders or grants dispatch permissions.
All uncertain observations remain STOPPED and require human intervention.
"""
from __future__ import annotations
import json, os, sqlite3, time
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing

ROOT=Path(__file__).resolve().parent
DB="weex_supervised_incidents_v6.sqlite3"
REPORT="weex_supervised_incident_v6_latest.json"
EXPECTED_SCOPE="ETHUSDT_100X_SUPERVISED_CRASH_V4"

def decide(*,control_mode,integrity,unknown,watchdog,account=None):
    base={"entryRetryAllowed":False,"closeRetryAllowed":False,
          "entryDispatchAllowed":False,"closeDispatchAllowed":False,
          "releaseCertified":False,"exchangeWrites":0}
    if control_mode!="STOPPED" or not integrity:
        return dict(base,status="CRITICAL_PRODUCTION_STATE",manualInterventionRequired=True)
    if not unknown:
        return dict(base,status="NO_PENDING_CRASH_INTENT",manualInterventionRequired=False)
    if not isinstance(watchdog,dict) or watchdog.get("scope")!=EXPECTED_SCOPE:
        return dict(base,status="UNKNOWN_ENTRY_SUPERVISOR_UNVERIFIED",manualInterventionRequired=True)
    status=watchdog.get("status")
    if status=="PROTECTED_EXACT_CLOSE_READY_FOR_SEPARATE_APPROVAL":
        if not isinstance(account,dict) or not account.get("fresh"):
            return dict(base,status="READBACK_STALE",manualInterventionRequired=True)
        if not (account.get("oneExactPosition") is True and account.get("oneExactStop") is True
                and account.get("noOtherOrders") is True and
                account.get("noAdditionalTargetConditional") is True and
                str(account.get("positionId"))==str(watchdog.get("positionId")) and
                str(account.get("stopAlgoId"))==str(watchdog.get("stopAlgoId"))):
            return dict(base,status="EXPOSURE_MISMATCH",manualInterventionRequired=True)
        return dict(base,status="VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL",
                    manualInterventionRequired=True,
                    positionId=str(account["positionId"]),stopAlgoId=str(account["stopAlgoId"]))
    return dict(base,status="UNKNOWN_OR_UNPROTECTED_EXPOSURE",manualInterventionRequired=True)

def independent_account_snapshot(root, *, reader=None, observed_at=None):
    """Fresh independent WEEX GET confirmation; never uses cached account state."""
    from weex_live_worker import Reader
    r=reader if reader is not None else Reader(root)
    start=time.time()
    positions, regular, conditional=r.account()
    end=time.time()
    if end-start>5 or (observed_at is not None and
        not 0<=end-float(observed_at)<=5):
        return {"fresh":False}
    if any(not isinstance(x,list) for x in (positions,regular,conditional)):
        return {"fresh":False}
    from weex_supervised_ownership_scope_v11 import split_exact_symbol
    scope=split_exact_symbol(positions,regular,conditional)
    exact_positions=scope['targetPositions']
    exact_stops=scope['targetConditional']
    position=exact_positions[0] if len(exact_positions)==1 else {}
    stop=exact_stops[0] if len(exact_stops)==1 else {}
    return {
        "fresh":True,
        "oneExactPosition":bool(position and position.get("side")=="LONG" and
            str(position.get("size")) in ("0.001","0.0010","0.00100") and
            str(position.get("id","")).isdigit()),
        "oneExactStop":bool(stop and stop.get("side")=="SELL" and
            stop.get("positionSide")=="LONG" and stop.get("reduceOnly") is True and
            str(stop.get("quantity")) in ("0.001","0.0010","0.00100") and
            str(stop.get("algoId","")).isdigit()),
        "noOtherOrders":scope['targetRegular']==[],
        "noAdditionalTargetConditional":len(exact_stops)==1,
        "foreignExposurePresent":scope['foreignExposurePresent'],
        "foreignSymbols":scope['foreignSymbols'],
        "positionId":str(position.get("id","")),
        "stopAlgoId":str(stop.get("algoId","")),
    }

def record(db,observation):
    """Durable single-row-by-id incident chronology; never overwrites history."""
    db=Path(db)
    db.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db,timeout=8)) as c:
        c.execute("PRAGMA busy_timeout=8000")
        c.execute("CREATE TABLE IF NOT EXISTS incidents (sequence INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL)")
        c.execute("BEGIN IMMEDIATE")
        # A continuously running supervisor must not append the same status
        # thousands of times per day. Preserve transitions and an hourly
        # heartbeat in the durable history; the latest JSON updates each tick.
        previous=c.execute('SELECT timestamp,status FROM incidents ORDER BY sequence DESC LIMIT 1').fetchone()
        at=time.time()
        if previous is None or previous[1]!=observation['status'] or at-float(previous[0])>=3600:
            c.execute("INSERT INTO incidents(timestamp,status,data) VALUES (?,?,?)",
                      (at,observation["status"],json.dumps(observation,sort_keys=True)))
        c.commit()

def observe(root=ROOT,*,watchdog_fn=None,account_fn=None,unknown_fn=None,control_fn=None):
    """Only reads existing local production and exchange state; defaults fail closed."""
    root=Path(root)
    try:
        import live_control
        from weex_supervised_crash_watchdog_v4 import observe as watchdog_observe,has_unknown_entry
        from weex_supervised_crash_executor_v2 import CLIENT_ID
        control=(control_fn or (lambda: (live_control.state(root)["mode"],
                 not live_control.build_errors(root))))()
        unknown=(unknown_fn or (lambda:has_unknown_entry(root,CLIENT_ID)))()
        watch=(watchdog_fn or (lambda:watchdog_observe(root)))()
        if unknown and isinstance(watch,dict) and watch.get('status')=='PROTECTED_EXACT_CLOSE_READY_FOR_SEPARATE_APPROVAL':
            account=(account_fn or (lambda:independent_account_snapshot(root)))()
        else:
            account=None
        result=decide(control_mode=control[0],integrity=control[1],
                      unknown=unknown,watchdog=watch,account=account)
    except Exception as exc:
        result={"status":"SUPERVISOR_READBACK_ERROR","errorType":type(exc).__name__,
                "entryRetryAllowed":False,"closeRetryAllowed":False,
                "entryDispatchAllowed":False,"closeDispatchAllowed":False,
                "releaseCertified":False,"manualInterventionRequired":True,"exchangeWrites":0}
    report={"checkedAt":datetime.now(timezone.utc).isoformat(),"mode":"READ_ONLY",
            "scope":"ETHUSDT_V6_SUPERVISION",**result}
    record(root/DB,report)
    target=root/REPORT
    tmp=target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    os.replace(tmp,target)
    return report

if __name__=="__main__":
    print(json.dumps(observe(),ensure_ascii=False))
