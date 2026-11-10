"""Read immutable live bot bindings from existing local ledger, never create or infer ownership."""
import sqlite3
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parent
def bindings(path=None):
 p=Path(path or ROOT/"execution_intents.sqlite3")
 if not p.exists():return []
 with closing(sqlite3.connect(f"file:{p.as_posix()}?mode=ro",uri=True)) as db:
  tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if "client_bindings" not in tables:return []
  rows=db.execute("SELECT intent_id,client_id FROM client_bindings").fetchall()
  # Ledger has no verified exchange orderId: report candidates only, never mark verified.
  return [{"intentId":i,"clientOrderId":c,"verified":False} for i,c in rows]
