"""One-shot live entry preflight for Telegram; GET-only, never submits orders."""
import json,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _age(stamp):
    return time.time()-datetime.fromisoformat(str(stamp).replace("Z","+00:00")).timestamp()

def inspect(root=ROOT):
    root=Path(root)
    cfg=_load(root/"weex_ai_risk_config.json")
    mode_file=root/"weex_simple_bot_latest.json"
    scan=_load(mode_file)
    if scan.get("ordersSubmitted") is not False:
        return {"status":"BLOCKED","reason":"SCAN_NOT_READ_ONLY","ordersSubmitted":False}
    if not 0<=_age(scan.get("checkedAt"))<=720:
        return {"status":"WAIT","reason":"SCANNER_REPORT_STALE","ordersSubmitted":False}
    from weex_live_worker import Reader,capture
    rows=[r for r in scan.get("results",[]) if r.get("marketSignal") in ("LONG","SHORT")
          and (r.get("realOrderBook") or {}).get("passed") is True
          and (r.get("realOrderBook") or {}).get("depthUnitVerified") is True]
    rows.sort(key=lambda r:(r.get("momentum") or {}).get("volumeRatio",0),reverse=True)
    if not rows:
        return {"status":"WAIT","reason":"NO_BOOK_VERIFIED_SIGNAL","ordersSubmitted":False}
    symbol=rows[0]["symbol"];scanned_side=rows[0]["marketSignal"]
    reader=Reader(root)
    try:
        plan,ctx,signal=capture(reader,symbol,cfg,notify_missing_tp=False)
    except Exception as exc:
        return {"status":"BLOCKED","symbol":symbol,"scannedSide":scanned_side,
                "reason":str(exc) if type(exc) in (ValueError,PermissionError) else type(exc).__name__,
                "ordersSubmitted":False}
    if signal.get("decision")!=scanned_side:
        return {"status":"WAIT","symbol":symbol,"scannedSide":scanned_side,
                "freshSide":signal.get("decision"),"reason":"SIGNAL_CHANGED_DURING_PREFLIGHT",
                "ordersSubmitted":False}
    occupied=any(x.get("symbol")==symbol for group in
                 (ctx.get("positions",[]),ctx.get("openOrders",[]),ctx.get("conditionalOrders",[]))
                 for x in group)
    from weex_capacity import account_capacity,lifecycle_position_ids
    cap=account_capacity(ctx.get("positions",[]),
        ctx.get("openOrders",[])+ctx.get("conditionalOrders",[]),
        managed_position_ids=lifecycle_position_ids(root/"weex_user_live_lifecycle.sqlite3"))
    from live_control import readiness,state
    from weex_trading_modes import get_mode
    errors=readiness(root);gate=_load(root/"live_release_gate_latest.json")
    trading_mode=get_mode(root)["mode"];live_switch=state(root)["mode"]
    if trading_mode=="alerts_only":blockers_mode=["TRADING_MODE_ALERTS_ONLY"]
    else:blockers_mode=[]
    if live_switch!="RUNNING":blockers_mode.append("LIVE_SWITCH_STOPPED")
    preview=plan.get("orderPreview",{})
    blockers=list(plan.get("blockers",[]))
    if occupied:blockers.append("SYMBOL_OCCUPIED")
    if cap.get("count",0)>=cfg["telegramSettings"]["maxConcurrentPositions"]["default"]:
        blockers.append("POSITION_LIMIT_REACHED")
    if cfg.get("execution",{}).get("enabled") is not False:
        blockers.append("EXECUTION_CONFIG_CHANGED")
    else:
        blockers.append("EXECUTION_DISABLED_PREVIEW_ONLY")
    if ctx.get("accountCanTrade") is not True:
        blockers.append("ACCOUNT_CANNOT_TRADE_OR_UNVERIFIED")
    if ctx.get("apiEnabled") is not True:
        blockers.append("SYMBOL_NOT_API_ENABLED")
    result={
      "status":"PREVIEW_ONLY",
      "checkedAt":datetime.now(timezone.utc).isoformat(),
      "symbol":symbol,"side":signal.get("decision"),
      "signalObservedAt":signal.get("observedAt"),
      "closedCandleTimes":signal.get("closedCandleTimes"),
      "volumeRatio":(signal.get("momentum") or {}).get("volumeRatio"),
      "book":{"status":"OK" if ctx.get("marketDataValid") else "UNAVAILABLE",
              "depthUnitVerified":ctx.get("depthUnitVerified"),
              "liquidityPassed":ctx.get("liquidityPassed")},
      "account":{"positions":len(ctx.get("positions",[])),
                 "capacityUsed":cap.get("count"),"capacityMax":cfg["telegramSettings"]["maxConcurrentPositions"]["default"],
                 "manualPositionsExcluded":cap.get("manualPositionsExcluded"),
                 "availableBalanceUSDT":ctx.get("availableBalance"),"canTrade":ctx.get("accountCanTrade")},
      "order":{"type":"MARKET","marginMode":"CROSS","costUSDT":str(cfg["risk"]["orderCostTargetUSDT"]),
               "costIncludesEntryFee":cfg["risk"].get("entryBudgetMode")=="COST_INCLUDING_ENTRY_FEE",
               "requestedLeverage":plan.get("requestedLeverage"),
               "currentCrossLeverage":plan.get("actualCrossLeverage"),
               "minimumLeverage":cfg["risk"].get("minimumLeverage"),
               "takerFeeRate":plan.get("exitFeeRate"),
               "feeRateSource":plan.get("feeRateSource"),
               "targetNetProfitUSDT":plan.get("targetNetProfitUSDT"),
               "tpPrice":preview.get("tpTriggerPrice"),"sl":"OFF"},
      "mode":{"tradingMode":trading_mode,"liveSwitch":live_switch,
              "executionEnabled":cfg["execution"].get("enabled"),
              "releaseGate":gate.get("gate"),"releasePassed":gate.get("passed"),
              "releaseTotal":gate.get("total"),"readinessErrors":errors},
      "blockers":sorted(set(blockers+blockers_mode+errors)),
      "ordersSubmitted":False,
      "notice":"Preflight only. This command cannot open a position or authorize LIVE execution."
    }
    return result

def telegram_text(root=ROOT):
    r=inspect(root)
    if r.get("status")!="PREVIEW_ONLY":
        return ("🧪 LIVE TEST — SOLO VERIFICA\n"
                f"Esito: {r.get('status')}\n"
                f"Pair: {r.get('symbol','n/d')} {r.get('scannedSide',r.get('side',''))}\n"
                f"Motivo: {r.get('reason','nessun candidato valido')}\n"
                "Ordine inviato: NO.")
    o=r["order"];a=r["account"];m=r["mode"]
    blocks=", ".join(r["blockers"]) if r["blockers"] else "nessuno nel preflight"
    return ("🧪 LIVE TEST — SOLO VERIFICA, NESSUN ORDINE\n"
            f"Coppia: {r['symbol']} {r['side']} | volume {r.get('volumeRatio')}×\n"
            f"Book: unità verificate={r['book']['depthUnitVerified']} | liquidità={r['book']['liquidityPassed']}\n"
            f"Conto: capacità {a['capacityUsed']}/{a['capacityMax']} | manuali esclusi={a['manualPositionsExcluded']} | saldo disponibile {a['availableBalanceUSDT']} USDT\n"
            f"Ordine previsto: Market Cross | Cost {o['costUSDT']} USDT (fee incluse: {o['costIncludesEntryFee']})\n"
            f"Leva: {o['currentCrossLeverage']}× attuale → {o['requestedLeverage']}× richiesta "
            f"(min {o['minimumLeverage']}×)\n"
            f"TP: {o['tpPrice']} | target netto stimato +{o['targetNetProfitUSDT']} USDT | SL OFF\n"
            f"Modalità: {m['tradingMode']} | switch {m['liveSwitch']} | execution={m['executionEnabled']}\n"
            f"Gate: {m['releaseGate']} {m['releasePassed']}/{m['releaseTotal']}\n"
            f"Blocchi: {blocks}\nOrdine inviato: NO.")
