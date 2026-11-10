"""Crash and duplicate-order fault tests on an isolated temporary SQLite DB. NO EXCHANGE WRITES."""
import tempfile,sqlite3,json
from pathlib import Path
from datetime import datetime,timezone
from demo_intent_binding import register,uncertain,reconcile
from crash_recovery_readonly import assess
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
 db=Path(folder)/"intents.db"
 client=register("BTCSUSDT",db=db)
 assert uncertain(client,db)
 rows=[{"clientOrderId":client,"orderId":"demo-test-42","origQty":"0.01","executedQty":"0.005","status":"PARTIALLY_FILLED"}]
 state1=assess([{"intent_id":"virtual-1","client_id":client}],rows,True)
 assert state1["canResume"],state1
 state2=assess([{"intent_id":"virtual-1","client_id":client}],rows+rows,True)
 assert not state2["canResume"],state2
 assert reconcile(client,rows,db)
 with sqlite3.connect(db) as c:
  persisted=c.execute("select state,exchange_id from demo_intents where client_id=?",(client,)).fetchone()
 assert persisted==("ACKNOWLEDGED","demo-test-42")
 report={"checkedAt":datetime.now(timezone.utc).isoformat(),"checks":{"partial_fill_restart":True,"duplicate_exchange_response_blocked":True,"persistent_binding":True},"exchangeOrdersSent":0,"note":"Offline synthetic simulation only"}
 path=Path(__file__).resolve().parent/"demo_recovery_fault_test_latest.json"
 path.write_text(json.dumps(report,indent=2),encoding="utf-8")
 print("OFFLINE_FAULT_TEST 3/3 PASS; REAL_ORDERS 0")
