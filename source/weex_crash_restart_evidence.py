"""Fault-injection proof for durable no-retry after a process dies at dispatch.

Uses the production Lifecycle with a temporary database and a crash-only fake
gateway. It performs no network, WEEX writes, or Telegram sends.
"""
import subprocess
import sys
import tempfile
from pathlib import Path


def run_fault_injection(timeout=8):
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="weex-crash-proof-") as folder:
        db = str(Path(folder) / "isolated.sqlite3")
        child = r"""
import os, sys
from weex_lifecycle import Lifecycle
cfg = {"execution":{"enabled":True,"mode":"LIVE"},"risk":{"minimumLeverage":125}}
class CrashAfterDurableCommit:
    def write(self, operation, payload):
        os._exit(73)
engine = Lifecycle(sys.argv[1], CrashAfterDurableCommit(), lambda: cfg)
plan = {
 "orderPreview":{"symbol":"ETHUSDT","side":"BUY","positionSide":"LONG","type":"MARKET","quantity":"0.001"},
 "requestedLeverage":"125","targetNetProfitUSDT":"10","beforePositions":[],
 "sizing":{}
}
item = engine.prepare("isolated-crash-recovery-probe", plan)
engine.send_once(item["id"],"MARGIN","post_capi_v3_account_marginType",
                 {"symbol":"ETHUSDT","marginType":"CROSSED"})
raise SystemExit(74)
"""
        try:
            crashed = subprocess.run([sys.executable, "-c", child, db], cwd=root,
                                     capture_output=True, text=True, timeout=timeout)
            from weex_lifecycle import Lifecycle
            class NoWriteAfterRestart:
                calls = 0
                def write(self, operation, payload):
                    self.calls += 1
                    raise AssertionError("RETRY_AFTER_RESTART")
                def read(self, operation, **query):
                    raise AssertionError("UNEXPECTED_READ")
            gateway = NoWriteAfterRestart()
            restarted = Lifecycle(db, gateway, lambda: {"execution":{"enabled":True,"mode":"LIVE"},"risk":{"minimumLeverage":125}})
            states = restarted.states()
            if len(states) != 1:
                return {"passed":False,"reason":"PERSISTED_TRADE_MISSING"}
            trade_id = states[0]["id"]
            item = restarted.get(trade_id)
            write = restarted.writes(trade_id).get("MARGIN")
            retry = restarted.send_once(trade_id,"MARGIN","post_capi_v3_account_marginType",
                                        {"symbol":"ETHUSDT","marginType":"CROSSED"})
            passed = (crashed.returncode == 73 and item["state"] == "PREPARED"
                      and write is not None and write["state"] == "UNKNOWN"
                      and retry["state"] == "RECONCILE_NO_RETRY" and gateway.calls == 0)
            return {
                "passed":passed,
                "childExitCode":crashed.returncode,
                "durableWriteState":write["state"] if write else None,
                "restartDecision":retry.get("state"),
                "retriesAfterRestart":gateway.calls,
                "networkRequests":0,"exchangeWrites":0,"telegramMessagesSent":0,
                "scope":"Production Lifecycle; isolated temporary DB; crash immediately after durable intent commit."
            }
        except Exception as exc:
            return {"passed":False,"reason":type(exc).__name__,
                    "networkRequests":0,"exchangeWrites":0,"telegramMessagesSent":0}


if __name__ == "__main__":
    result = run_fault_injection()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
