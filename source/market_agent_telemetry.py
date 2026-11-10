"""Persistent heartbeat and decision history for WEEX diagnostic agents. No trading."""
import json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"market_agent_telemetry.sqlite3"
def utc():return datetime.now(timezone.utc).isoformat()
def connect():
 c=sqlite3.connect(DB,timeout=10)
 c.execute("PRAGMA busy_timeout=10000")
 c.execute("CREATE TABLE IF NOT EXISTS heartbeat(agent TEXT PRIMARY KEY,observed_at TEXT NOT NULL,state TEXT NOT NULL,detail TEXT)")
 c.execute("CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,symbol TEXT,decision TEXT,observed_at TEXT,reasons TEXT, UNIQUE(run_id,symbol))")
 return c
def record(report):
 t=utc()
 run=report["asOf"]
 source=datetime.fromisoformat(run.replace("Z","+00:00"))
 age=(datetime.now(timezone.utc)-source).total_seconds()
 if not 0<=age<=420:raise ValueError("STALE_SOURCE_HEARTBEAT")
 if report.get("liveTrading") is not False:raise ValueError("Only read-only reports permitted")
 with closing(connect()) as c, c:
  for r in report.get("results",[]):
   symbol=r.get("symbol")
   if not symbol:continue
   decision=r.get("decision","ERROR")
   if decision not in ("LONG","SHORT","WAIT","ERROR"):raise ValueError("Unknown decision")
   c.execute("INSERT OR IGNORE INTO decisions(run_id,symbol,decision,observed_at,reasons) VALUES (?,?,?,?,?)",(run,symbol,decision,t,json.dumps(r.get("reasons",[]))))
  count=len(report.get("results",[]))
  c.execute("INSERT INTO heartbeat VALUES (?,?,?,?) ON CONFLICT(agent) DO UPDATE SET observed_at=excluded.observed_at,state=excluded.state,detail=excluded.detail",("market_diagnostics",run,"OBSERVED",f"{count} symbols; recorded {t}"))
 return count
def status():
 with closing(connect()) as c:
  return {"heartbeats":c.execute("SELECT agent,observed_at,state,detail FROM heartbeat").fetchall(),
          "decisions":c.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]}
if __name__=="__main__":
 x=json.loads((ROOT/"market_agents_latest.json").read_text(encoding="utf-8"))
 print("recorded",record(x),"status",status())
