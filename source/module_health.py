"""Module-level telemetry derived from actual WEEX diagnostic output. Read-only."""
import json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"market_agent_telemetry.sqlite3"
NAMES=("trend","momentum","liquidity_book","strategy")
def refresh():
 report=json.loads((ROOT/"market_agents_latest.json").read_text(encoding="utf-8"))
 if report.get("liveTrading") is not False:raise ValueError("Unexpected trading status")
 dt=datetime.fromisoformat(report["asOf"].replace("Z","+00:00"))
 n=len(report.get("results",[]))
 if n==0:raise ValueError("Empty diagnostic report")
 counts={
  "trend":sum("trend" in r for r in report["results"]),
  "momentum":sum("momentum" in r for r in report["results"]),
  "liquidity_book":sum(r.get("realOrderBook",{}).get("status")=="OK" for r in report["results"]),
  "strategy":sum(r.get("decision") in ("LONG","SHORT","WAIT") for r in report["results"])
 }
 with closing(sqlite3.connect(DB)) as db,db:
  db.execute("CREATE TABLE IF NOT EXISTS module_health(name TEXT PRIMARY KEY, source_at TEXT, checked_at TEXT, state TEXT, observations INTEGER, note TEXT)")
  for name in NAMES:
   count=counts[name]
   status="OBSERVED" if count>0 else "MISSING"
   note="Book observed; unit verification and sufficient depth are separate checks" if name=="liquidity_book" else "Diagnostic analysis; not independent agent process"
   db.execute("INSERT INTO module_health VALUES (?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET source_at=excluded.source_at,checked_at=excluded.checked_at,state=excluded.state,observations=excluded.observations,note=excluded.note",(name,report["asOf"],datetime.now(timezone.utc).isoformat(),status,count,note))
  db.execute("DELETE FROM module_health WHERE name='liquidity_proxy'")
 return counts
def state():
 with closing(sqlite3.connect(DB)) as db:
  rows=db.execute("SELECT name,source_at,state,observations,note FROM module_health").fetchall()
 return {name:{"sourceAt":at,"state":s,"observations":n,"note":note} for name,at,s,n,note in rows}
if __name__=="__main__":
 print("module observations",refresh())
